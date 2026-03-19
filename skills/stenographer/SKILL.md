---
name: stenographer
description: >
  Export conversation transcripts to Markdown, JSON, or HTML for sharing,
  archiving, or blog writing. Parses Claude Code JSONL session files and
  renders them as clean, human-readable documents. Use when the user asks
  to "export this conversation", "save transcript", "share this session",
  or "turn this into a blog post".
argument-hint: "[--format md|json|html] [--output file] [--blog] [--list]"
allowed-tools: Bash(python *), Bash(python3 *), Read, Write, Glob
---

# Stenographer

Export Claude Code conversation transcripts to Markdown, JSON, or HTML.

## Usage

Parse `$ARGUMENTS` for the following flags:

| Flag | Description |
|------|-------------|
| `--format md\|json\|html` | Output format (default: `md`) |
| `--output FILE` | Write to file instead of presenting inline |
| `--blog` | Blog-ready mode — clean narrative, no tool noise |
| `--list` | List available sessions for this project |
| `--include-thinking` | Include thinking/reasoning blocks |
| `--include-subagents` | Inline full subagent transcripts |
| `--verbose-tools` | Show full tool inputs and outputs |
| `--no-tool-details` | Hide tool calls entirely |
| `--clipboard` | Copy output to clipboard |

## Workflows

### 1. List Sessions

If `--list` is in the arguments:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/stenographer.py --list --project-dir "${CLAUDE_PROJECT_DIR}"
```

Present the output as a table of available sessions.

### 2. Export Transcript

Build the command from the parsed arguments:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/stenographer.py ${CLAUDE_SESSION_ID} [flags] --project-dir "${CLAUDE_PROJECT_DIR}"
```

If no session ID is provided and `$CLAUDE_SESSION_ID` is available, use the current session.

Pass through any flags from `$ARGUMENTS` directly to the script.

### 3. Blog Mode

If `--blog` is in the arguments:

1. Run the script with `--blog --no-tool-details` flags to get a clean transcript
2. Post-process the output: rewrite it into narrative form suitable for a blog post
3. Remove timestamps, session metadata, and role headers
4. Turn the conversation flow into a coherent story with proper transitions
5. Present the result or write to `--output` file

### 4. Output Handling

- If `--output` is specified: the script writes directly to the file
- If `--clipboard` is specified: pipe output to clipboard (`clip.exe` on Windows, `pbcopy` on macOS, `xclip` on Linux)
- Otherwise: present the output inline in the conversation

## Conventions

- Always use `python3` to run the script
- The script is zero-dependency — uses only Python standard library
- Session IDs are UUIDs (e.g., `a2478bb3-c968-4e9a-a57f-a69d6d3c7a85`)
- The `--project-dir` flag passes the encoded project directory name (e.g., `C--Users-sandm-temp`)
- If `$CLAUDE_PROJECT_DIR` is not available, derive it from `$CWD` by replacing `:\` with `--` and `\` with `-`
