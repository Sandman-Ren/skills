# Skills

Agent skills for Claude Code and other coding agents.

## Installation

```bash
npx skills add Sandman-Ren/skills
```

Or install a specific skill:

```bash
npx skills add Sandman-Ren/skills --skill create-workspace -g
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

**Workspace structure:**

```
my-workspace/
├── workspace.yaml              # manifest: repos, worktrees, deps
├── CLAUDE.md                   # project-wide agent context
├── .gitignore                  # ignores sketch/
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

**Triggers:** "create a workspace", "set up a multi-repo project", "add a repo to the workspace", "create a worktree"

## License

MIT
