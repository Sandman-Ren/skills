---
name: create-workspace
description: >
  Create and manage multi-repo development workspaces for complex tasks involving
  multiple repositories, dependencies, and parallel agent work. Use when the user
  wants to set up a workspace, add repos/worktrees/deps to an existing workspace,
  or initialize a project that spans multiple repositories. Triggers on requests like
  "create a workspace", "set up a multi-repo project", "add a repo to the workspace",
  or "create a worktree".
---

# Create Workspace

A skill for scaffolding structured, multi-repo development workspaces optimized for
parallel work by multiple agents and human developers.

## Workspace Structure

```
{workspace-name}/
├── workspace.yaml              # manifest: repos, worktrees, deps, metadata
├── CLAUDE.md                   # project-wide agent context and conventions
├── .gitignore                  # ignores sketch/ directory
├── .claude/
│   └── settings.json           # permissions for coding agents
├── repositories/
│   └── {repoName}/
│       ├── main/               # regular clone at default branch (worktree parent)
│       └── worktrees/
│           └── {worktreeName}/ # git worktree checkouts
├── docs/                       # cross-repo design docs, ADRs, specs
├── deps/
│   └── {depName}/              # full clones of dependency repos
├── tasks/                      # task assignments and coordination
└── sketch/                     # .gitignored agent scratch space
```

## Workflows

### 1. Create a New Workspace

When the user asks to create a workspace, follow these steps:

**Step 1: Gather information.** Ask the user for:
- Workspace name (will be the root directory name)
- A short description of the project/task
- Repository URLs to include (and which worktrees/branches to create)
- Dependency repository URLs (if any)

If the user provides a `workspace.yaml` file or its contents, parse it directly instead of asking.

**Step 2: Create the directory structure.**

```bash
mkdir -p {workspace-name}/{repositories,docs,deps,tasks,sketch}
```

**Step 3: Generate the workspace.yaml manifest.**

Use the template from `assets/workspace.yaml.template` as a reference. The manifest should
capture all repositories, their worktrees, and dependencies. Write it to `{workspace-name}/workspace.yaml`.

**Step 4: Clone repositories and create worktrees.**

For each repository in the manifest:

```bash
# Clone the repository into the main/ directory
git clone {url} {workspace-name}/repositories/{repoName}/main

# For each worktree, create a branch and worktree
cd {workspace-name}/repositories/{repoName}/main
git worktree add ../worktrees/{worktreeName} -b {branchName}
```

If the branch already exists on the remote, use checkout instead of `-b`:

```bash
git worktree add ../worktrees/{worktreeName} {branchName}
```

**Important worktree notes:**
- The `main/` clone is the worktree parent. Agents should avoid switching branches in `main/`.
- Each worktree is an independent working directory with its own HEAD, index, and working tree.
- Multiple agents can work on different worktrees of the same repo simultaneously without conflicts.

**Step 5: Clone dependencies.**

For each dependency in the manifest:

```bash
# Full clone (not shallow — deps may contain bugs or ongoing work to analyze)
git clone {url} {workspace-name}/deps/{depName}

# If a specific ref is specified, check it out
cd {workspace-name}/deps/{depName}
git checkout {ref}
```

**Step 6: Generate the CLAUDE.md.**

Use the template from `assets/CLAUDE.md.template` as a starting point. Populate it with:
- The workspace description from the manifest
- The list of repositories with their purposes
- The list of worktrees and what each is for
- The list of dependencies
- Cross-repo relationships (ask the user if not obvious)

**Step 7: Create the .gitignore.**

Write a `.gitignore` at the workspace root:

```
sketch/
```

**Step 8: Set up agent permissions.**

Create `.claude/settings.json` at the workspace root using the template from `assets/settings.json.template`. This file configures permissions so that coding agents can perform common development tasks without requiring manual approval for every command, while still blocking dangerous operations.

```bash
mkdir -p {workspace-name}/.claude
```

Copy the template as-is. The defaults are designed to be safe for multi-repo development:

- **Allow (no prompt):** Read-only tools, git read ops, git worktree management, build/test/lint commands for common package managers, file exploration, version checks.
- **Ask (prompt once):** Git write ops (commit, push, pull, merge, rebase), package installs, docker operations.
- **Deny (always blocked):** `rm -rf`, `sudo`, force pushes, `git reset --hard`, reading `.env`/`.env.local`/`.env.*.local`, secrets, SSH keys, AWS credentials, PEM/key files.

Note: `.env.example` and `.env.template` files are intentionally **not** blocked — agents need to read these to understand the environment variable setup.

This file is generated once. Users can edit it afterwards to add project-specific rules.

**Step 9: Confirm completion.** Summarize what was created:
- Number of repositories cloned
- Number of worktrees created
- Number of dependencies cloned
- Location of the workspace

### 2. Add a Repository to an Existing Workspace

When the user asks to add a repo to an existing workspace:

1. Read the existing `workspace.yaml`
2. Clone the repo into `repositories/{repoName}/main/`
3. Create any requested worktrees
4. Update `workspace.yaml` with the new repository entry
5. Update `CLAUDE.md` to include the new repository

### 3. Add a Worktree to an Existing Repository

When the user asks to add a worktree:

1. Read `workspace.yaml` to find the repository
2. Create the worktree:
   ```bash
   cd {workspace}/repositories/{repoName}/main
   git worktree add ../worktrees/{worktreeName} -b {branchName}
   ```
3. Update `workspace.yaml` with the new worktree entry

### 4. Add a Dependency

When the user asks to add a dependency:

1. Clone the dependency into `deps/{depName}/`
2. Optionally check out a specific ref
3. Update `workspace.yaml`
4. Update `CLAUDE.md`

### 5. Show Workspace Status

When the user asks about workspace status:

1. Read `workspace.yaml`
2. For each repository and worktree, run `git status` and `git log --oneline -3`
3. Report: current branches, uncommitted changes, recent commits

### 6. Remove a Worktree

When the user asks to remove a worktree:

1. Run `git worktree remove` from the main clone
2. Update `workspace.yaml`

## Conventions

- **Never modify the `main/` clone's branch** — it anchors all worktrees. Document this in CLAUDE.md.
- **Worktree names should match branch names** when possible for clarity. If the branch has slashes (e.g., `feature/auth`), use a slugified name for the worktree directory (e.g., `feature-auth`).
- **The `sketch/` directory is ephemeral** — agents can write anything there. It is always gitignored.
- **The `tasks/` directory** is for coordination between agents and humans. Files here describe work items, assignments, and status.
- **The `docs/` directory** is for durable design documentation that outlives any single task.

## Error Handling

- If a `git clone` fails, report the error and continue with remaining repos. Mark failed repos in the output.
- If a worktree branch already exists locally, use `git worktree add ../worktrees/{name} {branch}` without `-b`.
- If a worktree directory already exists, warn the user and skip unless they confirm overwriting.
- If `workspace.yaml` already exists when creating a new workspace, ask before overwriting.
