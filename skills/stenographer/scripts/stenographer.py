#!/usr/bin/env python3
"""Stenographer — Export Claude Code conversation transcripts.

Parses JSONL session files and renders them as Markdown, JSON, or HTML.
Zero external dependencies — uses only the Python standard library.
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ToolCall:
    tool_use_id: str
    name: str
    input_data: dict
    result: Optional[str] = None

    def summary(self) -> str:
        """One-line summary of what this tool call did."""
        inp = self.input_data
        name = self.name

        if name == "Bash":
            cmd = inp.get("command", "")
            desc = inp.get("description", "")
            display = desc if desc else cmd
            if len(display) > 200:
                display = display[:200] + "..."
            return f"Bash: `{display}`"

        if name == "Read":
            return f"Read: {inp.get('file_path', '?')}"

        if name == "Write":
            return f"Write to {inp.get('file_path', '?')}"

        if name == "Edit":
            return f"Edit {inp.get('file_path', '?')}"

        if name == "Glob":
            return f"Glob: {inp.get('pattern', '?')}"

        if name == "Grep":
            path = inp.get("path", ".")
            return f"Grep: `{inp.get('pattern', '?')}` in {path}"

        if name == "Agent":
            return f"Subagent: \"{inp.get('description', inp.get('prompt', '?')[:60])}\""

        if name == "WebFetch":
            return f"Fetch: {inp.get('url', '?')}"

        if name == "WebSearch":
            return f"Search: \"{inp.get('query', '?')}\""

        if name == "Skill":
            return f"Skill: /{inp.get('skill', '?')}"

        # Generic fallback
        short_inp = str(inp)
        if len(short_inp) > 100:
            short_inp = short_inp[:100] + "..."
        return f"{name}: {short_inp}"

    def truncated_result(self, max_lines: int = 5) -> Optional[str]:
        """Return result truncated to max_lines."""
        if not self.result:
            return None
        lines = self.result.split("\n")
        if len(lines) <= max_lines:
            return self.result
        shown = "\n".join(lines[:max_lines])
        remaining = len(lines) - max_lines
        return f"{shown}\n... ({remaining} more lines)"


@dataclass
class Message:
    role: str  # "user", "assistant", "system"
    content: str  # Text content (joined from content blocks)
    timestamp: Optional[str] = None
    uuid: Optional[str] = None
    parent_uuid: Optional[str] = None
    tool_calls: list = field(default_factory=list)  # List[ToolCall]
    thinking: Optional[str] = None
    model: Optional[str] = None
    is_tool_result: bool = False
    raw_type: Optional[str] = None  # "user", "assistant", "progress", etc.


@dataclass
class SubagentInfo:
    agent_id: str
    agent_type: str = ""
    description: str = ""
    message_count: int = 0
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None
    messages: list = field(default_factory=list)  # For --include-subagents

    @property
    def duration(self) -> str:
        if not self.first_ts or not self.last_ts:
            return "?"
        try:
            t1 = datetime.fromisoformat(self.first_ts.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(self.last_ts.replace("Z", "+00:00"))
            delta = (t2 - t1).total_seconds()
            if delta < 60:
                return f"{int(delta)}s"
            return f"{int(delta // 60)}m {int(delta % 60)}s"
        except (ValueError, TypeError):
            return "?"


# ---------------------------------------------------------------------------
# Session parser
# ---------------------------------------------------------------------------

class SessionParser:
    """Parse a Claude Code JSONL session file into a linear conversation."""

    CLAUDE_DIR = Path.home() / ".claude" / "projects"

    def __init__(self, project_dir: Optional[str] = None):
        self.project_dir = project_dir

    def _resolve_project_path(self) -> Path:
        """Resolve the project directory under ~/.claude/projects/."""
        if self.project_dir:
            return self.CLAUDE_DIR / self.project_dir
        # Derive from CWD
        cwd = os.getcwd()
        encoded = cwd.replace(":", "-").replace("\\", "-").replace("/", "-")
        return self.CLAUDE_DIR / encoded

    def list_sessions(self) -> list[dict]:
        """List available sessions for this project."""
        proj_path = self._resolve_project_path()
        if not proj_path.exists():
            return []

        sessions = []
        for f in sorted(proj_path.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
            session_id = f.stem
            # Read first user message for preview
            preview = ""
            timestamp = ""
            msg_count = 0
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if obj.get("type") in ("user", "assistant"):
                            msg_count += 1
                        if not preview and obj.get("type") == "user":
                            msg = obj.get("message", {})
                            content = msg.get("content", "")
                            if isinstance(content, str) and content:
                                # Skip internal messages for preview
                                if content.strip().startswith(("<local-command-", "<command-name>")):
                                    continue
                                preview = content[:120]
                                timestamp = obj.get("timestamp", "")
                            elif isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get("type") == "text":
                                        preview = block.get("text", "")[:120]
                                        timestamp = obj.get("timestamp", "")
                                        break
                                    elif isinstance(block, str):
                                        preview = block[:120]
                                        timestamp = obj.get("timestamp", "")
                                        break
            except (OSError, IOError):
                continue

            if msg_count > 0:
                sessions.append({
                    "session_id": session_id,
                    "timestamp": timestamp,
                    "messages": msg_count,
                    "preview": preview.replace("\n", " "),
                    "file": str(f),
                })
        return sessions

    def parse(self, session_id: str, include_subagents: bool = False) -> tuple[list[Message], dict, dict[str, SubagentInfo]]:
        """Parse a session JSONL file.

        Returns (messages, metadata, subagents).
        """
        proj_path = self._resolve_project_path()
        jsonl_path = proj_path / f"{session_id}.jsonl"
        if not jsonl_path.exists():
            raise FileNotFoundError(f"Session file not found: {jsonl_path}")

        # Read all records
        records = []
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Build tree and linearize
        uuid_to_record = {}
        children = {}  # parentUuid -> [records in file order]
        roots = []
        subagents: dict[str, SubagentInfo] = {}

        for rec in records:
            rec_type = rec.get("type", "")
            uuid = rec.get("uuid")

            # Skip file-history-snapshot
            if rec_type == "file-history-snapshot":
                continue

            # Collect subagent info from progress events
            if rec_type == "progress":
                data = rec.get("data", {})
                agent_id = data.get("agentId")
                if agent_id:
                    if agent_id not in subagents:
                        subagents[agent_id] = SubagentInfo(agent_id=agent_id)
                    sa = subagents[agent_id]
                    ts = rec.get("timestamp")
                    sa.message_count += 1
                    if not sa.first_ts:
                        sa.first_ts = ts
                    sa.last_ts = ts

                    # Extract inner message for subagent transcript
                    if include_subagents:
                        inner_msg = data.get("message", {})
                        if inner_msg:
                            sa.messages.append(inner_msg)
                continue

            if uuid:
                uuid_to_record[uuid] = rec
                parent = rec.get("parentUuid")
                if parent is None:
                    roots.append(rec)
                else:
                    children.setdefault(parent, []).append(rec)

        # Read subagent meta.json files
        subagent_dir = proj_path / session_id / "subagents"
        if subagent_dir.exists():
            for meta_file in subagent_dir.glob("*.meta.json"):
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    # Extract agent ID from filename: agent-XXXX.meta.json
                    agent_id_match = re.match(r"agent-(.+)\.meta\.json", meta_file.name)
                    if agent_id_match:
                        aid = agent_id_match.group(1)
                        # Try matching with 'a' prefix too
                        for key in [aid, f"a{aid}"]:
                            if key in subagents:
                                subagents[key].agent_type = meta.get("agentType", "")
                                subagents[key].description = meta.get("description", "")
                                break
                        else:
                            # Create entry even if no progress events matched
                            subagents[aid] = SubagentInfo(
                                agent_id=aid,
                                agent_type=meta.get("agentType", ""),
                                description=meta.get("description", ""),
                            )
                except (json.JSONDecodeError, OSError):
                    continue

        # Also try to read full subagent JSONL if --include-subagents
        if include_subagents and subagent_dir.exists():
            for sa_jsonl in subagent_dir.glob("*.jsonl"):
                agent_id_match = re.match(r"agent-(.+)\.jsonl", sa_jsonl.name)
                if not agent_id_match:
                    continue
                aid = agent_id_match.group(1)
                # Find matching subagent
                sa_key = None
                for key in [aid, f"a{aid}"]:
                    if key in subagents:
                        sa_key = key
                        break
                if sa_key is None:
                    sa_key = aid
                    subagents[sa_key] = SubagentInfo(agent_id=aid)

                sa = subagents[sa_key]
                if not sa.messages:  # Don't overwrite if already populated from progress events
                    try:
                        with open(sa_jsonl, "r", encoding="utf-8") as f:
                            for line in f:
                                line = line.strip()
                                if not line:
                                    continue
                                try:
                                    obj = json.loads(line)
                                    if obj.get("type") in ("user", "assistant"):
                                        sa.messages.append(obj)
                                        sa.message_count = max(sa.message_count, len(sa.messages))
                                        ts = obj.get("timestamp")
                                        if ts:
                                            if not sa.first_ts:
                                                sa.first_ts = ts
                                            sa.last_ts = ts
                                except json.JSONDecodeError:
                                    continue
                    except (OSError, IOError):
                        continue

        # Linearize: follow the last child at each step (active branch)
        linear = []
        if roots:
            current = roots[-1]  # Latest root
            linear.append(current)
            while True:
                uuid = current.get("uuid")
                kids = children.get(uuid, [])
                if not kids:
                    break
                current = kids[-1]  # Latest child = active branch
                linear.append(current)

        # Build tool call map: tool_use_id -> ToolCall
        tool_calls_by_id = {}

        # First pass: collect all tool_use blocks
        for rec in linear:
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message", {})
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tc = ToolCall(
                        tool_use_id=block.get("id", ""),
                        name=block.get("name", ""),
                        input_data=block.get("input", {}),
                    )
                    tool_calls_by_id[tc.tool_use_id] = tc

        # Second pass: match tool results
        for rec in linear:
            if rec.get("type") != "user":
                continue
            msg = rec.get("message", {})
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tuid = block.get("tool_use_id", "")
                    result_content = block.get("content", "")
                    if isinstance(result_content, list):
                        # Content can be a list of text blocks
                        parts = []
                        for part in result_content:
                            if isinstance(part, dict):
                                parts.append(part.get("text", str(part)))
                            else:
                                parts.append(str(part))
                        result_content = "\n".join(parts)
                    if tuid in tool_calls_by_id:
                        tool_calls_by_id[tuid].result = result_content

        # Build messages
        messages = []
        metadata = {"session_id": session_id}

        # Track which tool_use_ids have been consumed as tool results
        consumed_tool_results = set()
        for rec in linear:
            if rec.get("type") != "user":
                continue
            msg = rec.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        consumed_tool_results.add(block.get("tool_use_id", ""))

        for rec in linear:
            rec_type = rec.get("type")
            ts = rec.get("timestamp")
            uuid = rec.get("uuid")
            parent = rec.get("parentUuid")

            if rec_type == "assistant":
                msg = rec.get("message", {})
                content_blocks = msg.get("content", [])
                model = msg.get("model")

                if model and "model" not in metadata:
                    metadata["model"] = model

                text_parts = []
                thinking_text = None
                msg_tool_calls = []

                if isinstance(content_blocks, list):
                    for block in content_blocks:
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "text":
                            text = block.get("text", "")
                            if text.strip():
                                text_parts.append(text)
                        elif btype == "thinking":
                            thinking_text = block.get("thinking", "")
                        elif btype == "tool_use":
                            tuid = block.get("id", "")
                            if tuid in tool_calls_by_id:
                                msg_tool_calls.append(tool_calls_by_id[tuid])

                content_str = "\n".join(text_parts)
                # Skip empty assistant chunks (streaming artifacts)
                if not content_str and not msg_tool_calls and not thinking_text:
                    continue

                messages.append(Message(
                    role="assistant",
                    content=content_str,
                    timestamp=ts,
                    uuid=uuid,
                    parent_uuid=parent,
                    tool_calls=msg_tool_calls,
                    thinking=thinking_text,
                    model=model,
                    raw_type=rec_type,
                ))

            elif rec_type == "user":
                msg = rec.get("message", {})
                content = msg.get("content", "")

                # Skip pure tool-result messages
                is_tool_result = False
                if isinstance(content, list):
                    all_tool_results = all(
                        isinstance(b, dict) and b.get("type") == "tool_result"
                        for b in content if isinstance(b, dict)
                    )
                    if all_tool_results and content:
                        is_tool_result = True

                if is_tool_result:
                    continue

                # Extract text from content
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            parts.append(block)
                    text = "\n".join(parts)
                else:
                    text = str(content)

                if not text.strip():
                    continue

                # Skip internal/system messages (slash commands, local-command output)
                stripped = text.strip()
                if stripped.startswith("<local-command-caveat>"):
                    continue
                if stripped.startswith("<command-name>"):
                    continue
                if stripped.startswith("<local-command-stdout>"):
                    continue
                if stripped.startswith("[Request interrupted"):
                    continue

                # Get date from first user message
                if "date" not in metadata and ts:
                    metadata["date"] = ts

                messages.append(Message(
                    role="user",
                    content=text,
                    timestamp=ts,
                    uuid=uuid,
                    parent_uuid=parent,
                    raw_type=rec_type,
                ))

        return messages, metadata, subagents


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _format_time(ts: Optional[str]) -> str:
    """Format ISO timestamp to HH:MM."""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return ""


def _format_date(ts: Optional[str]) -> str:
    """Format ISO timestamp to YYYY-MM-DD."""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


class MarkdownRenderer:
    """Render conversation as Markdown."""

    def __init__(self, include_thinking: bool = False, verbose_tools: bool = False,
                 no_tool_details: bool = False, include_subagents: bool = False,
                 blog_mode: bool = False):
        self.include_thinking = include_thinking
        self.verbose_tools = verbose_tools
        self.no_tool_details = no_tool_details
        self.include_subagents = include_subagents
        self.blog_mode = blog_mode

    def render(self, messages: list[Message], metadata: dict,
               subagents: dict[str, SubagentInfo]) -> str:
        lines = []

        if not self.blog_mode:
            lines.append("# Conversation Transcript")
            meta_parts = []
            if metadata.get("session_id"):
                meta_parts.append(f"**Session**: {metadata['session_id'][:8]}")
            if metadata.get("date"):
                meta_parts.append(f"**Date**: {_format_date(metadata['date'])}")
            if metadata.get("model"):
                meta_parts.append(f"**Model**: {metadata['model']}")
            if meta_parts:
                lines.append(" | ".join(meta_parts))
            lines.append("")
            lines.append("---")
            lines.append("")

        # Merge consecutive assistant messages
        merged = self._merge_consecutive(messages)

        for msg in merged:
            time_str = _format_time(msg.timestamp)

            if self.blog_mode:
                if msg.role == "user":
                    lines.append(f"**User**: {msg.content}")
                else:
                    lines.append(msg.content)
                lines.append("")
                continue

            role_label = "User" if msg.role == "user" else "Claude"
            time_suffix = f" ({time_str})" if time_str else ""
            lines.append(f"## {role_label}{time_suffix}")
            lines.append("")

            if msg.thinking and self.include_thinking:
                lines.append("<details>")
                lines.append("<summary>Thinking</summary>")
                lines.append("")
                lines.append(msg.thinking)
                lines.append("")
                lines.append("</details>")
                lines.append("")

            if msg.content and msg.content.strip():
                lines.append(msg.content.strip())
                lines.append("")

            if not self.no_tool_details:
                for tc in msg.tool_calls:
                    summary = tc.summary()
                    lines.append(f"> **{summary}**")
                    if self.verbose_tools and tc.result:
                        lines.append(f"> ```")
                        for result_line in tc.result.split("\n"):
                            lines.append(f"> {result_line}")
                        lines.append(f"> ```")
                    elif tc.result:
                        truncated = tc.truncated_result()
                        if truncated:
                            lines.append(f"> ```")
                            for result_line in truncated.split("\n"):
                                lines.append(f"> {result_line}")
                            lines.append(f"> ```")
                    lines.append("")

            # Show subagent references from tool calls
            if not self.no_tool_details:
                for tc in msg.tool_calls:
                    if tc.name == "Agent":
                        desc = tc.input_data.get("description", "")
                        # Find matching subagent info
                        for sa in subagents.values():
                            if sa.description == desc or desc in sa.description:
                                sa_type = f" ({sa.agent_type})" if sa.agent_type else ""
                                lines.append(
                                    f'> **Subagent{sa_type}**: "{sa.description}" '
                                    f"({sa.message_count} messages, {sa.duration})"
                                )
                                lines.append("")

                                if self.include_subagents and sa.messages:
                                    lines.append("<details>")
                                    lines.append(f"<summary>Subagent transcript: {sa.description}</summary>")
                                    lines.append("")
                                    self._render_subagent_messages(lines, sa)
                                    lines.append("</details>")
                                    lines.append("")
                                break

        return "\n".join(lines)

    def _merge_consecutive(self, messages: list[Message]) -> list[Message]:
        """Merge consecutive assistant messages into one."""
        merged = []
        for msg in messages:
            if (merged and merged[-1].role == msg.role == "assistant"):
                prev = merged[-1]
                parts = []
                if prev.content:
                    parts.append(prev.content)
                if msg.content:
                    parts.append(msg.content)
                prev.content = "\n\n".join(parts) if parts else ""
                prev.tool_calls.extend(msg.tool_calls)
                if msg.thinking and not prev.thinking:
                    prev.thinking = msg.thinking
            else:
                merged.append(msg)
        return merged

    def _render_subagent_messages(self, lines: list[str], sa: SubagentInfo):
        """Render subagent messages as nested content."""
        for raw in sa.messages:
            if isinstance(raw, dict):
                msg_obj = raw.get("message", raw)
                role = msg_obj.get("role", raw.get("type", "?"))
                content = msg_obj.get("content", "")

                if isinstance(content, str) and content.strip():
                    lines.append(f"**{role.title()}**: {content.strip()}")
                    lines.append("")
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text" and block.get("text", "").strip():
                                lines.append(f"**{role.title()}**: {block['text'].strip()}")
                                lines.append("")
                            elif block.get("type") == "tool_use":
                                name = block.get("name", "?")
                                lines.append(f"> *{name}*")
                                lines.append("")


class JsonRenderer:
    """Render conversation as structured JSON."""

    def __init__(self, include_thinking: bool = False, verbose_tools: bool = False,
                 no_tool_details: bool = False, include_subagents: bool = False):
        self.include_thinking = include_thinking
        self.verbose_tools = verbose_tools
        self.no_tool_details = no_tool_details
        self.include_subagents = include_subagents

    def render(self, messages: list[Message], metadata: dict,
               subagents: dict[str, SubagentInfo]) -> str:
        output = {
            "session_id": metadata.get("session_id", ""),
            "metadata": {
                "model": metadata.get("model", ""),
                "date": _format_date(metadata.get("date")),
                "project": metadata.get("project_dir", ""),
            },
            "messages": [],
        }

        for msg in messages:
            entry = {
                "role": msg.role,
                "timestamp": msg.timestamp,
                "content": msg.content,
            }

            if msg.thinking and self.include_thinking:
                entry["thinking"] = msg.thinking

            if not self.no_tool_details and msg.tool_calls:
                entry["tool_calls"] = []
                for tc in msg.tool_calls:
                    tc_entry = {
                        "name": tc.name,
                        "summary": tc.summary(),
                    }
                    if self.verbose_tools:
                        tc_entry["input"] = tc.input_data
                        tc_entry["result"] = tc.result
                    else:
                        tc_entry["result_preview"] = tc.truncated_result()
                    entry["tool_calls"].append(tc_entry)

            output["messages"].append(entry)

        if self.include_subagents and subagents:
            output["subagents"] = {}
            for aid, sa in subagents.items():
                output["subagents"][aid] = {
                    "type": sa.agent_type,
                    "description": sa.description,
                    "message_count": sa.message_count,
                    "duration": sa.duration,
                }

        return json.dumps(output, indent=2, ensure_ascii=False)


class HtmlRenderer:
    """Render conversation as self-contained HTML."""

    def __init__(self, include_thinking: bool = False, verbose_tools: bool = False,
                 no_tool_details: bool = False, include_subagents: bool = False,
                 template_path: Optional[Path] = None):
        self.include_thinking = include_thinking
        self.verbose_tools = verbose_tools
        self.no_tool_details = no_tool_details
        self.include_subagents = include_subagents
        self.template_path = template_path or (
            Path(__file__).parent.parent / "templates" / "transcript.html"
        )

    def _escape(self, text: str) -> str:
        return html.escape(text)

    def _md_to_html(self, text: str) -> str:
        """Minimal Markdown-to-HTML conversion."""
        result = self._escape(text)

        # Code blocks: ```lang\n...\n```
        def replace_code_block(m):
            lang = m.group(1) or ""
            code = m.group(2)
            return f'<pre><code class="language-{lang}">{code}</code></pre>'
        result = re.sub(r'```(\w*)\n(.*?)```', replace_code_block, result, flags=re.DOTALL)

        # Inline code
        result = re.sub(r'`([^`]+)`', r'<code>\1</code>', result)

        # Bold
        result = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', result)

        # Italic
        result = re.sub(r'\*(.+?)\*', r'<em>\1</em>', result)

        # Convert line breaks to paragraphs
        paragraphs = result.split("\n\n")
        paragraphs = [f"<p>{p.strip()}</p>" for p in paragraphs if p.strip()]
        return "\n".join(paragraphs)

    def render(self, messages: list[Message], metadata: dict,
               subagents: dict[str, SubagentInfo]) -> str:
        # Load template
        try:
            template = self.template_path.read_text(encoding="utf-8")
        except (OSError, IOError):
            # Fallback: minimal template
            template = (
                "<!DOCTYPE html><html><head><title>{{TITLE}}</title></head>"
                "<body>{{METADATA}}{{CONTENT}}</body></html>"
            )

        # Build metadata
        meta_parts = []
        if metadata.get("session_id"):
            sid = metadata["session_id"][:8]
            meta_parts.append(f"<span>Session: {self._escape(sid)}</span>")
        if metadata.get("date"):
            meta_parts.append(f"<span>Date: {_format_date(metadata['date'])}</span>")
        if metadata.get("model"):
            meta_parts.append(f"<span>Model: {self._escape(metadata['model'])}</span>")

        # Merge consecutive assistant messages
        merged = self._merge_consecutive(messages)

        # Build content
        content_parts = []
        for msg in merged:
            time_str = _format_time(msg.timestamp)
            role_class = f"role-{msg.role}"
            msg_class = f"message-{msg.role}"
            role_label = "User" if msg.role == "user" else "Claude"

            parts = []
            parts.append(f'<div class="message {msg_class}">')
            parts.append(f'  <div class="message-header">')
            parts.append(f'    <span class="role {role_class}">{role_label}</span>')
            if time_str:
                parts.append(f'    <span class="timestamp">{time_str}</span>')
            parts.append(f'  </div>')

            if msg.thinking and self.include_thinking:
                parts.append(f'  <details class="thinking">')
                parts.append(f'    <summary>Thinking</summary>')
                parts.append(f'    {self._md_to_html(msg.thinking)}')
                parts.append(f'  </details>')

            if msg.content:
                parts.append(f'  <div class="content">{self._md_to_html(msg.content)}</div>')

            if not self.no_tool_details:
                for tc in msg.tool_calls:
                    summary = self._escape(tc.summary())
                    parts.append(f'  <details class="tool-call">')
                    parts.append(f'    <summary>{summary}</summary>')
                    if tc.result:
                        result_text = tc.result if self.verbose_tools else (tc.truncated_result() or "")
                        parts.append(f'    <div class="tool-result">{self._escape(result_text)}</div>')
                    parts.append(f'  </details>')

                # Subagent summaries
                for tc in msg.tool_calls:
                    if tc.name == "Agent":
                        desc = tc.input_data.get("description", "")
                        for sa in subagents.values():
                            if sa.description == desc or desc in sa.description:
                                sa_label = self._escape(sa.description)
                                sa_type = f" ({self._escape(sa.agent_type)})" if sa.agent_type else ""
                                parts.append(
                                    f'  <div class="subagent">'
                                    f'Subagent{sa_type}: "{sa_label}" '
                                    f'({sa.message_count} messages, {sa.duration})'
                                    f'</div>'
                                )
                                break

            parts.append(f'</div>')
            content_parts.append("\n".join(parts))

        title = f"Transcript — {metadata.get('session_id', 'session')[:8]}"
        content_html = "\n\n".join(content_parts)
        meta_html = "\n    ".join(meta_parts)

        result = template.replace("{{TITLE}}", self._escape(title))
        result = result.replace("{{METADATA}}", meta_html)
        result = result.replace("{{CONTENT}}", content_html)
        return result

    def _merge_consecutive(self, messages: list[Message]) -> list[Message]:
        """Merge consecutive assistant messages."""
        merged = []
        for msg in messages:
            if merged and merged[-1].role == msg.role == "assistant":
                prev = merged[-1]
                parts = []
                if prev.content:
                    parts.append(prev.content)
                if msg.content:
                    parts.append(msg.content)
                prev.content = "\n\n".join(parts) if parts else ""
                prev.tool_calls.extend(msg.tool_calls)
                if msg.thinking and not prev.thinking:
                    prev.thinking = msg.thinking
            else:
                merged.append(msg)
        return merged


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def copy_to_clipboard(text: str):
    """Copy text to system clipboard."""
    if sys.platform == "win32":
        # Use clip.exe (works in both Windows and WSL)
        try:
            proc = subprocess.run(["clip.exe"], input=text.encode("utf-16-le"),
                                  check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    elif sys.platform == "darwin":
        try:
            subprocess.run(["pbcopy"], input=text.encode(), check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
    else:
        for cmd in ["xclip -selection clipboard", "xsel --clipboard"]:
            try:
                subprocess.run(cmd.split(), input=text.encode(), check=True, capture_output=True)
                return True
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Export Claude Code conversation transcripts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "session_id", nargs="?", default=None,
        help='Session UUID or "current" (default: $CLAUDE_SESSION_ID)',
    )
    parser.add_argument("--format", choices=["markdown", "md", "json", "html"],
                        default="markdown", dest="fmt",
                        help="Output format (default: markdown)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Write to file (default: stdout)")
    parser.add_argument("--project-dir", type=str, default=None,
                        help="Override project directory name")
    parser.add_argument("--include-thinking", action="store_true",
                        help="Include thinking/reasoning blocks")
    parser.add_argument("--include-subagents", action="store_true",
                        help="Inline full subagent transcripts")
    parser.add_argument("--verbose-tools", action="store_true",
                        help="Show full tool inputs and outputs")
    parser.add_argument("--no-tool-details", action="store_true",
                        help="Hide tool calls entirely")
    parser.add_argument("--blog", action="store_true",
                        help="Blog-ready mode (clean, narrative-friendly)")
    parser.add_argument("--list", action="store_true",
                        help="List available sessions")
    parser.add_argument("--clipboard", action="store_true",
                        help="Copy output to clipboard")

    args = parser.parse_args()

    # Resolve session ID
    session_id = args.session_id
    if not session_id or session_id == "current":
        session_id = os.environ.get("CLAUDE_SESSION_ID")

    session_parser = SessionParser(project_dir=args.project_dir)

    # List mode
    if args.list:
        sessions = session_parser.list_sessions()
        if not sessions:
            print("No sessions found.", file=sys.stderr)
            sys.exit(1)

        # Table output
        print(f"{'Session ID':<40} {'Date':<12} {'Msgs':>5}  Preview")
        print("-" * 100)
        for s in sessions:
            date = _format_date(s["timestamp"])
            preview = s["preview"]
            if len(preview) > 60:
                preview = preview[:60] + "..."
            print(f"{s['session_id']:<40} {date:<12} {s['messages']:>5}  {preview}")
        sys.exit(0)

    if not session_id:
        print("Error: No session ID provided. Use a UUID, 'current', or set $CLAUDE_SESSION_ID.",
              file=sys.stderr)
        sys.exit(1)

    # Blog mode implies no tool details
    if args.blog:
        args.no_tool_details = True

    # Parse
    try:
        messages, metadata, subagents = session_parser.parse(
            session_id, include_subagents=args.include_subagents
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not messages:
        print("No messages found in session.", file=sys.stderr)
        sys.exit(1)

    metadata["project_dir"] = args.project_dir or ""

    # Render
    fmt = args.fmt
    if fmt in ("markdown", "md"):
        renderer = MarkdownRenderer(
            include_thinking=args.include_thinking,
            verbose_tools=args.verbose_tools,
            no_tool_details=args.no_tool_details,
            include_subagents=args.include_subagents,
            blog_mode=args.blog,
        )
    elif fmt == "json":
        renderer = JsonRenderer(
            include_thinking=args.include_thinking,
            verbose_tools=args.verbose_tools,
            no_tool_details=args.no_tool_details,
            include_subagents=args.include_subagents,
        )
    elif fmt == "html":
        renderer = HtmlRenderer(
            include_thinking=args.include_thinking,
            verbose_tools=args.verbose_tools,
            no_tool_details=args.no_tool_details,
            include_subagents=args.include_subagents,
        )
    else:
        print(f"Unknown format: {fmt}", file=sys.stderr)
        sys.exit(1)

    output = renderer.render(messages, metadata, subagents)

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    elif args.clipboard:
        if copy_to_clipboard(output):
            print("Copied to clipboard.", file=sys.stderr)
        else:
            print("Failed to copy to clipboard. Printing to stdout instead.", file=sys.stderr)
            print(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
