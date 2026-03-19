# Skills

Agent skills for Claude Code and other coding agents.

## Installation

```bash
npx skills add Sandman-Ren/skills
```

Or install a specific skill globally:

```bash
npx skills add Sandman-Ren/skills --skill create-workspace -g
```

## Updating

```bash
npx skills update
```

Or check for available updates first:

```bash
npx skills check
```

## Managing Skills

```bash
npx skills list       # view installed skills
npx skills remove     # uninstall a skill
```

## Available Skills

### create-workspace

Create and manage multi-repo development workspaces for complex tasks involving multiple repositories, dependencies, and parallel agent work.

**Features:**
- Scaffolds a structured workspace with `repositories/`, `docs/`, `deps/`, `tasks/`, and `sketch/` directories
- Clones repositories and sets up git worktrees for parallel development
- Generates a `workspace.yaml` manifest as the source of truth
- Creates a root `CLAUDE.md` with project context and agent conventions
- Supports adding/removing repos, worktrees, and dependencies to existing workspaces
- **Modular permission system** — add/remove permission modules for GitHub, Node.js, Python, Rust, Go, Docker, Playwright, Context7, and more
- Preview permissions before writing, add custom rules, all project-scoped

**Workspace structure:**

```
my-workspace/
├── workspace.yaml              # manifest: repos, worktrees, deps
├── CLAUDE.md                   # project-wide agent context
├── .gitignore                  # ignores sketch/
├── .claude/
│   └── settings.json           # modular agent permissions
├── repositories/
│   └── {repoName}/
│       ├── main/               # regular clone (worktree parent)
│       └── worktrees/
│           └── {worktreeName}/ # git worktree checkouts
├── docs/                       # cross-repo design docs, ADRs, specs
├── deps/
│   └── {depName}/              # full clones of dependency repos
├── tasks/                      # task assignments and coordination
└── sketch/                     # .gitignored agent scratch space
```

**Permission modules:**

| Module | What it covers |
|--------|---------------|
| `_base` | Read, Glob, Grep, git read-only, utilities (always included) |
| `_security` | Deny rules for destructive ops and sensitive files (always included) |
| `github` | GitHub MCP tools + `gh` CLI |
| `context7` | Library documentation lookup |
| `nodejs` | npm, yarn, pnpm, bun |
| `python` | pytest, mypy, ruff, pip, poetry, uv |
| `rust` | cargo build, test, clippy |
| `go` | go test, build, vet, mod |
| `docker` | Docker + Compose inspection and lifecycle |
| `playwright` | Browser automation and testing |

**Triggers:** "create a workspace", "set up a multi-repo project", "add a repo to the workspace", "create a worktree", "add github permissions", "set up workspace permissions"

### stenographer

Export conversation transcripts to Markdown, JSON, or HTML for sharing, archiving, or blog writing. Parses Claude Code JSONL session files and renders them as clean, human-readable documents.

**Features:**
- Parses JSONL session files with full tree linearization (handles branching conversations)
- Three output formats: Markdown, JSON, and HTML (self-contained dark theme)
- Tool call summarization with collapsible details
- Subagent detection and optional inline transcripts
- Blog mode for narrative-friendly output
- Clipboard support
- Session listing

**Flags:**

| Flag | Description |
|------|-------------|
| `--format md\|json\|html` | Output format (default: `md`) |
| `--output FILE` | Write to file |
| `--blog` | Blog-ready mode — clean narrative, no tool noise |
| `--list` | List available sessions |
| `--include-thinking` | Include thinking/reasoning blocks |
| `--include-subagents` | Inline full subagent transcripts |
| `--verbose-tools` | Show full tool inputs and outputs |
| `--no-tool-details` | Hide tool calls entirely |
| `--clipboard` | Copy output to clipboard |

**Triggers:** "export this conversation", "save transcript", "share this session", "turn this into a blog post"

## License

MIT
