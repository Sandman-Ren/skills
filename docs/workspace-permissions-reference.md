# Workspace Permissions Reference

Research document for enhancing the `create-workspace` skill with comprehensive
permission configuration — covering CLI commands, MCP tool permissions, and
security best practices.

## Table of Contents

- [Permission System Overview](#permission-system-overview)
- [Permission Rule Syntax](#permission-rule-syntax)
- [Pre-baked MCP Server Permissions](#pre-baked-mcp-server-permissions)
- [CLI Command Permissions](#cli-command-permissions)
- [Deny List — Dangerous Operations](#deny-list--dangerous-operations)
- [Sensitive File Access Deny Rules](#sensitive-file-access-deny-rules)
- [Runtime MCP Detection Strategy](#runtime-mcp-detection-strategy)
- [Security Considerations](#security-considerations)
- [Complete Reference Template](#complete-reference-template)
- [Sources](#sources)

---

## Permission System Overview

Claude Code uses a three-tier permission system:

| Tier     | Behavior                                                    |
| -------- | ----------------------------------------------------------- |
| **deny** | Blocked unconditionally. Evaluated first — always wins.     |
| **ask**  | Prompts user for confirmation before executing.             |
| **allow**| Auto-approved, no prompt needed.                            |

**Evaluation order:** deny → ask → allow. First matching rule wins.

### Permission Modes

| Mode                | Description                                                |
| ------------------- | ---------------------------------------------------------- |
| `default`           | Prompts for permission on first use of each tool           |
| `acceptEdits`       | Auto-accepts file edit permissions for the session         |
| `plan`              | Read-only — Claude can analyze but not modify              |
| `dontAsk`           | Auto-denies unless pre-approved via permissions            |
| `bypassPermissions` | Skips all prompts (unsafe — containers/VMs only)           |

---

## Permission Rule Syntax

Rules follow the format `Tool` or `Tool(specifier)`.

### Bash Commands

```
Bash                          # matches ALL bash commands
Bash(npm run build)           # exact match
Bash(npm run *)               # wildcard — prefix match with word boundary
Bash(npm*)                    # no space before * — matches npm, npx, etc.
Bash(* --version)             # wildcard at start
Bash(git * main)              # wildcard in middle
```

**Important:** Space before `*` enforces word boundary. `Bash(ls *)` matches
`ls -la` but not `lsof`. `Bash(ls*)` matches both.

**Shell operator safety:** Claude Code is aware of `&&`, `||`, `;`, `|` — a rule
like `Bash(safe-cmd *)` won't permit `safe-cmd && malicious-cmd`.

**Legacy syntax:** `Bash(cmd:*)` (colon-star) is deprecated but equivalent to
`Bash(cmd *)` (space-star).

### File Operations (Read / Edit / Write)

Follow gitignore specification with four path types:

| Pattern    | Meaning                          | Example                           |
| ---------- | -------------------------------- | --------------------------------- |
| `//path`   | Absolute filesystem path         | `Read(//Users/alice/secrets/**)` |
| `~/path`   | Relative to home directory       | `Read(~/Documents/*.pdf)`        |
| `/path`    | Relative to settings file        | `Edit(/src/**/*.ts)`             |
| `./path`   | Relative to current directory    | `Read(./**/.env)`                |

- `*` matches files in a single directory
- `**` matches recursively across directories
- Just `Read`, `Edit`, or `Write` (no parens) matches all file access

### MCP Tools

```
mcp__serverName                     # matches ALL tools from server
mcp__serverName__*                  # wildcard — also matches all tools
mcp__serverName__specific_tool      # matches one specific tool
```

The naming pattern is:
- Plugins: `mcp__plugin_{pluginName}_{serverName}__toolName`
- Custom/direct servers: `mcp__{serverName}__toolName`

### WebFetch

```
WebFetch                            # matches all web fetches
WebFetch(domain:example.com)        # matches specific domain
```

### Task (Subagents)

```
Task(Explore)                       # matches the Explore subagent
Task(Plan)                          # matches the Plan subagent
Task(my-custom-agent)               # matches a custom subagent
```

---

## Pre-baked MCP Server Permissions

These are commonly used MCP servers that should be pre-configured in every
workspace. The categorization follows the principle: **reads are allowed,
writes require confirmation, destructive operations are denied.**

### Context7

Two tools, both read-only. Safe to auto-allow.

| Tool | Permission | Rationale |
| ---- | ---------- | --------- |
| `mcp__context7__resolve-library-id` | **allow** | Read-only lookup — resolves library names to IDs |
| `mcp__context7__query-docs` | **allow** | Read-only — fetches documentation |

Alternative naming (plugin variant):
- `mcp__plugin_context7_context7__resolve-library-id`
- `mcp__plugin_context7_context7__query-docs`

**Note:** Both naming patterns may exist depending on how the server is
configured (direct vs plugin). Include both variants in the allow list to
cover either case, or use the wildcard `mcp__context7__*` and
`mcp__plugin_context7_context7__*`.

### GitHub MCP Server

41 tools total. Split by read (18) vs write (23).

#### Allow (read-only operations)

| Tool | Description |
| ---- | ----------- |
| `get_commit` | Get commit details |
| `get_file_contents` | Get file/directory contents from a repo |
| `get_label` | Get a specific label |
| `get_latest_release` | Get latest release |
| `get_me` | Get authenticated user info |
| `get_release_by_tag` | Get release by tag name |
| `get_tag` | Get git tag details |
| `get_team_members` | Get team member usernames |
| `get_teams` | Get user's team memberships |
| `issue_read` | Read issue details, comments, sub-issues, labels |
| `list_branches` | List repo branches |
| `list_commits` | List branch commits |
| `list_issue_types` | List supported issue types |
| `list_issues` | List/filter repo issues |
| `list_pull_requests` | List repo pull requests |
| `list_releases` | List repo releases |
| `list_tags` | List git tags |
| `pull_request_read` | Read PR details, diff, status, files, reviews, comments |
| `search_code` | Search code across GitHub repos |
| `search_issues` | Search issues across repos |
| `search_pull_requests` | Search PRs across repos |
| `search_repositories` | Search repositories |
| `search_users` | Search GitHub users |

#### Ask (write operations — require confirmation)

| Tool | Description |
| ---- | ----------- |
| `add_issue_comment` | Add comment to issue/PR |
| `add_reply_to_pull_request_comment` | Reply to PR comment |
| `create_branch` | Create a new branch |
| `create_pull_request` | Create a new PR |
| `create_repository` | Create a new repository |
| `issue_write` | Create or update an issue |
| `update_pull_request` | Update an existing PR |
| `update_pull_request_branch` | Update PR branch with base changes |
| `sub_issue_write` | Add/remove/reprioritize sub-issues |

#### Ask (higher-risk write operations)

| Tool | Description |
| ---- | ----------- |
| `add_comment_to_pending_review` | Add comment to pending review |
| `assign_copilot_to_issue` | Assign Copilot to an issue |
| `create_or_update_file` | Create/update file in remote repo |
| `delete_file` | Delete a file from a repo |
| `fork_repository` | Fork a repo |
| `merge_pull_request` | Merge a PR |
| `pull_request_review_write` | Create/submit/delete PR reviews |
| `push_files` | Push multiple files in a single commit |
| `request_copilot_review` | Request Copilot review |

**Permission format:**
```json
"mcp__plugin_github_github__get_file_contents"
"mcp__plugin_github_github__create_pull_request"
```

### Playwright MCP Server

22 tools total. Split by observation (5) vs interactive (17).

#### Allow (read-only / observation)

| Tool | Description |
| ---- | ----------- |
| `browser_snapshot` | Capture accessibility snapshot (preferred over screenshot) |
| `browser_take_screenshot` | Take page screenshot |
| `browser_console_messages` | Get browser console messages |
| `browser_network_requests` | Get network requests since page load |
| `browser_tabs` (list action) | List open browser tabs |

#### Ask (interactive / write operations)

| Tool | Description |
| ---- | ----------- |
| `browser_navigate` | Navigate to a URL |
| `browser_navigate_back` | Go back in browser history |
| `browser_click` | Click on a web element |
| `browser_type` | Type text into an element |
| `browser_fill_form` | Fill multiple form fields |
| `browser_press_key` | Press a keyboard key |
| `browser_hover` | Hover over an element |
| `browser_select_option` | Select dropdown option |
| `browser_drag` | Drag and drop between elements |
| `browser_file_upload` | Upload files |
| `browser_evaluate` | Execute JavaScript in browser |
| `browser_run_code` | Run Playwright code snippet |
| `browser_handle_dialog` | Handle browser dialogs |
| `browser_resize` | Resize browser window |
| `browser_close` | Close the browser |
| `browser_install` | Install browser |
| `browser_wait_for` | Wait for text/time |

**Permission format:**
```json
"mcp__plugin_playwright_playwright__browser_snapshot"
"mcp__plugin_playwright_playwright__browser_navigate"
```

---

## CLI Command Permissions

Organized by ecosystem. Follows the principle: **reads and builds are allowed,
installs and writes require confirmation, destructive operations are denied.**

### Git — Version Control

#### Allow (read-only)

```json
"Bash(git status *)",
"Bash(git diff *)",
"Bash(git log *)",
"Bash(git show *)",
"Bash(git branch *)",
"Bash(git stash list)",
"Bash(git worktree list)",
"Bash(git ls-files *)",
"Bash(git ls-tree *)",
"Bash(git rev-parse *)",
"Bash(git remote *)",
"Bash(git describe *)",
"Bash(git shortlog *)",
"Bash(git blame *)",
"Bash(git tag *)"
```

#### Allow (worktree management — core to multi-repo workspaces)

```json
"Bash(git worktree add *)",
"Bash(git worktree remove *)",
"Bash(git worktree prune)"
```

#### Ask (write operations)

```json
"Bash(git add *)",
"Bash(git commit *)",
"Bash(git push *)",
"Bash(git pull *)",
"Bash(git merge *)",
"Bash(git rebase *)",
"Bash(git checkout *)",
"Bash(git switch *)",
"Bash(git stash *)",
"Bash(git cherry-pick *)",
"Bash(git fetch *)"
```

#### Deny (destructive)

```json
"Bash(git push --force *)",
"Bash(git push -f *)",
"Bash(git reset --hard *)",
"Bash(git clean -f *)",
"Bash(git clean -fd *)",
"Bash(git clean -fx *)"
```

### Node.js / JavaScript Ecosystem

#### Allow (read-only and build/test/lint)

```json
"Bash(npm run *)",
"Bash(npm test *)",
"Bash(npm list *)",
"Bash(npm ls *)",
"Bash(npm outdated *)",
"Bash(npm audit *)",
"Bash(npm view *)",
"Bash(npm info *)",
"Bash(npm explain *)",
"Bash(npm why *)",
"Bash(npx prettier *)",
"Bash(npx eslint *)",
"Bash(npx tsc *)",
"Bash(npx vitest *)",
"Bash(npx jest *)",
"Bash(yarn run *)",
"Bash(yarn test *)",
"Bash(yarn info *)",
"Bash(yarn why *)",
"Bash(pnpm run *)",
"Bash(pnpm test *)",
"Bash(pnpm list *)",
"Bash(pnpm ls *)",
"Bash(pnpm outdated *)",
"Bash(pnpm why *)",
"Bash(bun run *)",
"Bash(bun test *)"
```

#### Ask (install / modify dependencies)

```json
"Bash(npm install *)",
"Bash(npm ci)",
"Bash(npm ci *)",
"Bash(npm uninstall *)",
"Bash(yarn install *)",
"Bash(yarn add *)",
"Bash(yarn remove *)",
"Bash(pnpm install *)",
"Bash(pnpm add *)",
"Bash(pnpm remove *)",
"Bash(bun install *)",
"Bash(bun add *)",
"Bash(bun remove *)"
```

### Python Ecosystem

#### Allow (read-only and test/lint)

```json
"Bash(python -m pytest *)",
"Bash(python3 -m pytest *)",
"Bash(python -m mypy *)",
"Bash(python3 -m mypy *)",
"Bash(python -m pylint *)",
"Bash(python3 -m pylint *)",
"Bash(python -m black --check *)",
"Bash(python3 -m black --check *)",
"Bash(python -m ruff check *)",
"Bash(python3 -m ruff check *)",
"Bash(python -c *)",
"Bash(python3 -c *)",
"Bash(poetry run *)",
"Bash(poetry show *)"
```

#### Ask (install / modify dependencies)

```json
"Bash(pip install *)",
"Bash(pip uninstall *)",
"Bash(pip3 install *)",
"Bash(pip3 uninstall *)",
"Bash(poetry install *)",
"Bash(poetry add *)",
"Bash(poetry remove *)",
"Bash(poetry lock *)",
"Bash(uv pip install *)",
"Bash(uv add *)"
```

### Rust Ecosystem

#### Allow (read-only and build/test/lint)

```json
"Bash(cargo test *)",
"Bash(cargo build *)",
"Bash(cargo check *)",
"Bash(cargo clippy *)",
"Bash(cargo doc *)",
"Bash(cargo bench *)",
"Bash(cargo tree *)",
"Bash(cargo metadata *)"
```

#### Ask (modify dependencies)

```json
"Bash(cargo add *)",
"Bash(cargo remove *)",
"Bash(cargo install *)",
"Bash(cargo update *)"
```

### Go Ecosystem

#### Allow (read-only and build/test/lint)

```json
"Bash(go test *)",
"Bash(go build *)",
"Bash(go vet *)",
"Bash(go doc *)",
"Bash(go list *)",
"Bash(go env *)",
"Bash(go version *)"
```

#### Ask (modify dependencies)

```json
"Bash(go mod *)",
"Bash(go get *)",
"Bash(go install *)"
```

### Docker

#### Allow (read-only / inspection)

```json
"Bash(docker ps *)",
"Bash(docker logs *)",
"Bash(docker inspect *)",
"Bash(docker images *)",
"Bash(docker network ls *)",
"Bash(docker network inspect *)",
"Bash(docker volume ls *)",
"Bash(docker stats --no-stream *)",
"Bash(docker compose ps *)",
"Bash(docker compose logs *)",
"Bash(docker compose config *)"
```

#### Ask (lifecycle operations)

```json
"Bash(docker build *)",
"Bash(docker run *)",
"Bash(docker exec *)",
"Bash(docker stop *)",
"Bash(docker start *)",
"Bash(docker restart *)",
"Bash(docker compose up *)",
"Bash(docker compose down *)",
"Bash(docker compose restart *)",
"Bash(docker compose build *)"
```

#### Deny (destructive)

```json
"Bash(docker system prune *)",
"Bash(docker volume prune *)",
"Bash(docker image prune *)"
```

### Make / Build Tools

#### Allow

```json
"Bash(make *)",
"Bash(cmake *)",
"Bash(gradle *)",
"Bash(mvn *)"
```

### General Utilities

#### Allow (safe, read-only)

```json
"Bash(ls *)",
"Bash(tree *)",
"Bash(pwd)",
"Bash(wc *)",
"Bash(which *)",
"Bash(where *)",
"Bash(whoami)",
"Bash(hostname)",
"Bash(* --version)",
"Bash(* --help)"
```

### GitHub CLI (gh)

#### Allow (read-only)

```json
"Bash(gh repo view *)",
"Bash(gh issue list *)",
"Bash(gh issue view *)",
"Bash(gh pr list *)",
"Bash(gh pr view *)",
"Bash(gh pr diff *)",
"Bash(gh pr checks *)",
"Bash(gh pr status *)",
"Bash(gh run list *)",
"Bash(gh run view *)",
"Bash(gh workflow list *)",
"Bash(gh api *)"
```

#### Ask (write operations)

```json
"Bash(gh pr create *)",
"Bash(gh pr merge *)",
"Bash(gh pr close *)",
"Bash(gh pr review *)",
"Bash(gh issue create *)",
"Bash(gh issue close *)",
"Bash(gh repo create *)"
```

---

## Deny List — Dangerous Operations

These operations should **always be denied** regardless of workspace type.
They are destructive, irreversible, or represent privilege escalation.

### File System Destruction

```json
"Bash(rm -rf *)",
"Bash(rm -r *)",
"Bash(rmdir *)",
"Bash(del /s *)",
"Bash(rd /s *)"
```

**Note:** `rm` (without `-rf`) is intentionally NOT denied. Single file
deletion is sometimes necessary. The deny targets recursive deletion only.

### Privilege Escalation

```json
"Bash(* sudo *)",
"Bash(sudo *)",
"Bash(su *)",
"Bash(runas *)",
"Bash(doas *)"
```

### Disk / Filesystem Destruction

```json
"Bash(dd *)",
"Bash(mkfs *)",
"Bash(fdisk *)",
"Bash(parted *)",
"Bash(format *)"
```

### Permission Abuse

```json
"Bash(chmod 777 *)",
"Bash(chmod -R 777 *)",
"Bash(chmod a+rwx *)"
```

### Git Destructive Operations

```json
"Bash(git push --force *)",
"Bash(git push -f *)",
"Bash(git reset --hard *)",
"Bash(git clean -f *)",
"Bash(git clean -fd *)",
"Bash(git clean -fx *)"
```

### Process / System Manipulation

```json
"Bash(kill -9 *)",
"Bash(killall *)",
"Bash(pkill -9 *)",
"Bash(shutdown *)",
"Bash(reboot *)",
"Bash(init *)",
"Bash(systemctl stop *)",
"Bash(systemctl disable *)"
```

### Network Exfiltration Risks

```json
"Bash(curl -X POST *)",
"Bash(curl --upload-file *)",
"Bash(wget --post-data *)",
"Bash(scp *)",
"Bash(rsync *)",
"Bash(ftp *)",
"Bash(sftp *)"
```

**Note:** Read-only `curl -s` / `curl --silent` for fetching data is
acceptable in many workflows. Only outbound data operations are denied.

### Cron / Scheduled Tasks

```json
"Bash(crontab -r *)",
"Bash(crontab -e *)",
"Bash(at *)",
"Bash(schtasks /create *)"
```

---

## Sensitive File Access Deny Rules

These files should **never** be read by agents. Applies to both `Read` and
`Bash(cat ...)` access.

### Environment / Secrets

```json
"Read(./**/.env)",
"Read(./**/.env.local)",
"Read(./**/.env.*.local)",
"Read(./**/secrets/**)",
"Read(./**/*credentials*)",
"Read(./**/*secret*)"
```

**Intentionally NOT blocked:**
- `.env.example` — agents need these to understand variable structure
- `.env.template` — same rationale

### SSH / Auth Keys

```json
"Read(~/.ssh/**)",
"Read(./**/*.pem)",
"Read(./**/*.key)",
"Read(./**/*.p12)",
"Read(./**/*.pfx)",
"Read(./**/*.jks)"
```

### Cloud Provider Credentials

```json
"Read(~/.aws/**)",
"Read(~/.kube/**)",
"Read(~/.config/gcloud/**)",
"Read(~/.azure/**)",
"Read(./**/*serviceAccount*.json)"
```

### Password / Token Files

```json
"Read(./**/.htpasswd)",
"Read(./**/.npmrc)",
"Read(./**/.pypirc)",
"Read(~/.netrc)",
"Read(./**/token*)",
"Read(./**/*password*)"
```

---

## Runtime MCP Detection Strategy

The skill should detect additional MCP servers at runtime and offer to
configure permissions for them. Here's the approach:

### Step 1: Discover MCP Servers

Read `~/.claude/settings.json` and look for:

1. **`mcpServers`** key — custom MCP servers with command/args config
2. **`enabledPlugins`** key — plugin-provided MCP servers
3. **Existing `mcp__*` permissions** — tools the user already allows globally

### Step 2: Map Plugin Names to Server Prefixes

Known mappings (from observed runtime behavior):

| Plugin Name | Permission Prefix |
| ----------- | ----------------- |
| `github@claude-plugins-official` | `mcp__plugin_github_github__` |
| `playwright@claude-plugins-official` | `mcp__plugin_playwright_playwright__` |
| `context7@claude-plugins-official` | `mcp__plugin_context7_context7__` |
| Custom MCP server named `foo` | `mcp__foo__` |

### Step 3: Prompt the User

For each detected MCP server NOT in the pre-baked list:

> "I detected these additional MCP servers: [cloudflare-docs, next-devtools].
> Would you like to add permissions for any of them?"

Options per server:
- **Allow all tools** — `mcp__serverName__*`
- **Ask for all tools** — adds to ask list
- **Skip** — no permissions added

### Step 4: Copy Global Permissions

For servers the user selects, mirror any `mcp__*` entries from their global
`~/.claude/settings.json` into the workspace's `.claude/settings.json`.

---

## Security Considerations

### Defense in Depth

Permissions and sandboxing are complementary layers:
- **Permissions** control which tools Claude can invoke
- **Sandboxing** (OS-level) restricts what Bash commands can actually access

Use both when available.

### Known Limitations

1. **Deny rules for Read/Write tools** have had enforcement bugs in some
   Claude Code versions. Using PreToolUse hooks provides more reliable
   blocking for critical deny rules.

2. **Sub-agents may bypass** deny rules in some versions. Test that deny
   rules apply to subagent contexts.

3. **Bash argument patterns are fragile** — `Bash(curl http://github.com/ *)`
   won't match `curl -X GET http://github.com/...` or reordered flags. For
   URL filtering, prefer `WebFetch(domain:...)` rules plus denying raw
   `curl`/`wget` in Bash.

4. **Wildcard MCP patterns** (`mcp__server__*`) have had intermittent issues
   where individual tools still prompt. Including explicit tool names
   alongside the wildcard improves reliability.

### Principle of Least Privilege

- Only allow what agents actually need for the workspace's tech stack
- Default unknown tools to **ask** rather than **allow**
- Pre-baked read-only MCP tools are safe to auto-allow
- Write operations should always require at least one confirmation
- Destructive operations should be denied outright

### Workspace-Specific Considerations

- Workspace-level `.claude/settings.json` permissions are additive to the
  user's global settings
- Project-level settings take precedence over user-level settings
- The workspace settings should add permissions relevant to the workspace's
  specific tech stack, not duplicate the user's global config

---

## Complete Reference Template

Below is the full `settings.json` template that the create-workspace skill
should generate. It combines pre-baked MCP permissions, CLI permissions, and
deny rules.

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "WebSearch",

      "// --- Context7 MCP (documentation lookup) ---",
      "mcp__context7__resolve-library-id",
      "mcp__context7__query-docs",
      "mcp__plugin_context7_context7__resolve-library-id",
      "mcp__plugin_context7_context7__query-docs",

      "// --- GitHub MCP (read operations) ---",
      "mcp__plugin_github_github__get_commit",
      "mcp__plugin_github_github__get_file_contents",
      "mcp__plugin_github_github__get_label",
      "mcp__plugin_github_github__get_latest_release",
      "mcp__plugin_github_github__get_me",
      "mcp__plugin_github_github__get_release_by_tag",
      "mcp__plugin_github_github__get_tag",
      "mcp__plugin_github_github__get_team_members",
      "mcp__plugin_github_github__get_teams",
      "mcp__plugin_github_github__issue_read",
      "mcp__plugin_github_github__list_branches",
      "mcp__plugin_github_github__list_commits",
      "mcp__plugin_github_github__list_issue_types",
      "mcp__plugin_github_github__list_issues",
      "mcp__plugin_github_github__list_pull_requests",
      "mcp__plugin_github_github__list_releases",
      "mcp__plugin_github_github__list_tags",
      "mcp__plugin_github_github__pull_request_read",
      "mcp__plugin_github_github__search_code",
      "mcp__plugin_github_github__search_issues",
      "mcp__plugin_github_github__search_pull_requests",
      "mcp__plugin_github_github__search_repositories",
      "mcp__plugin_github_github__search_users",

      "// --- Playwright MCP (observation) ---",
      "mcp__plugin_playwright_playwright__browser_snapshot",
      "mcp__plugin_playwright_playwright__browser_take_screenshot",
      "mcp__plugin_playwright_playwright__browser_console_messages",
      "mcp__plugin_playwright_playwright__browser_network_requests",

      "// --- Git (read-only) ---",
      "Bash(git status *)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(git show *)",
      "Bash(git branch *)",
      "Bash(git stash list)",
      "Bash(git worktree list)",
      "Bash(git ls-files *)",
      "Bash(git ls-tree *)",
      "Bash(git rev-parse *)",
      "Bash(git remote *)",
      "Bash(git describe *)",
      "Bash(git shortlog *)",
      "Bash(git blame *)",
      "Bash(git tag *)",

      "// --- Git worktree management ---",
      "Bash(git worktree add *)",
      "Bash(git worktree remove *)",
      "Bash(git worktree prune)",

      "// --- Node.js (build / test / lint) ---",
      "Bash(npm run *)",
      "Bash(npm test *)",
      "Bash(npm list *)",
      "Bash(npm ls *)",
      "Bash(npm outdated *)",
      "Bash(npm audit *)",
      "Bash(npm view *)",
      "Bash(npm info *)",
      "Bash(npm explain *)",
      "Bash(npm why *)",
      "Bash(npx prettier *)",
      "Bash(npx eslint *)",
      "Bash(npx tsc *)",
      "Bash(npx vitest *)",
      "Bash(npx jest *)",
      "Bash(yarn run *)",
      "Bash(yarn test *)",
      "Bash(yarn info *)",
      "Bash(yarn why *)",
      "Bash(pnpm run *)",
      "Bash(pnpm test *)",
      "Bash(pnpm list *)",
      "Bash(pnpm ls *)",
      "Bash(pnpm outdated *)",
      "Bash(pnpm why *)",
      "Bash(bun run *)",
      "Bash(bun test *)",

      "// --- Python (test / lint) ---",
      "Bash(python -m pytest *)",
      "Bash(python3 -m pytest *)",
      "Bash(python -m mypy *)",
      "Bash(python3 -m mypy *)",
      "Bash(python -m pylint *)",
      "Bash(python3 -m pylint *)",
      "Bash(python -m ruff check *)",
      "Bash(python3 -m ruff check *)",
      "Bash(python -c *)",
      "Bash(python3 -c *)",
      "Bash(poetry run *)",
      "Bash(poetry show *)",

      "// --- Rust (build / test / lint) ---",
      "Bash(cargo test *)",
      "Bash(cargo build *)",
      "Bash(cargo check *)",
      "Bash(cargo clippy *)",
      "Bash(cargo doc *)",
      "Bash(cargo bench *)",
      "Bash(cargo tree *)",
      "Bash(cargo metadata *)",

      "// --- Go (build / test / lint) ---",
      "Bash(go test *)",
      "Bash(go build *)",
      "Bash(go vet *)",
      "Bash(go doc *)",
      "Bash(go list *)",
      "Bash(go env *)",
      "Bash(go version *)",

      "// --- Docker (read-only / inspection) ---",
      "Bash(docker ps *)",
      "Bash(docker logs *)",
      "Bash(docker inspect *)",
      "Bash(docker images *)",
      "Bash(docker network ls *)",
      "Bash(docker network inspect *)",
      "Bash(docker volume ls *)",
      "Bash(docker stats --no-stream *)",
      "Bash(docker compose ps *)",
      "Bash(docker compose logs *)",
      "Bash(docker compose config *)",

      "// --- Build tools ---",
      "Bash(make *)",
      "Bash(cmake *)",
      "Bash(gradle *)",
      "Bash(mvn *)",

      "// --- GitHub CLI (read-only) ---",
      "Bash(gh repo view *)",
      "Bash(gh issue list *)",
      "Bash(gh issue view *)",
      "Bash(gh pr list *)",
      "Bash(gh pr view *)",
      "Bash(gh pr diff *)",
      "Bash(gh pr checks *)",
      "Bash(gh pr status *)",
      "Bash(gh run list *)",
      "Bash(gh run view *)",
      "Bash(gh workflow list *)",
      "Bash(gh api *)",

      "// --- General utilities ---",
      "Bash(ls *)",
      "Bash(tree *)",
      "Bash(pwd)",
      "Bash(wc *)",
      "Bash(which *)",
      "Bash(where *)",
      "Bash(whoami)",
      "Bash(hostname)",
      "Bash(* --version)",
      "Bash(* --help)"
    ],

    "ask": [
      "// --- GitHub MCP (write operations) ---",
      "mcp__plugin_github_github__add_issue_comment",
      "mcp__plugin_github_github__add_reply_to_pull_request_comment",
      "mcp__plugin_github_github__create_branch",
      "mcp__plugin_github_github__create_pull_request",
      "mcp__plugin_github_github__create_repository",
      "mcp__plugin_github_github__issue_write",
      "mcp__plugin_github_github__update_pull_request",
      "mcp__plugin_github_github__update_pull_request_branch",
      "mcp__plugin_github_github__sub_issue_write",
      "mcp__plugin_github_github__add_comment_to_pending_review",
      "mcp__plugin_github_github__assign_copilot_to_issue",
      "mcp__plugin_github_github__create_or_update_file",
      "mcp__plugin_github_github__delete_file",
      "mcp__plugin_github_github__fork_repository",
      "mcp__plugin_github_github__merge_pull_request",
      "mcp__plugin_github_github__pull_request_review_write",
      "mcp__plugin_github_github__push_files",
      "mcp__plugin_github_github__request_copilot_review",

      "// --- Playwright MCP (interactive) ---",
      "mcp__plugin_playwright_playwright__browser_navigate",
      "mcp__plugin_playwright_playwright__browser_navigate_back",
      "mcp__plugin_playwright_playwright__browser_click",
      "mcp__plugin_playwright_playwright__browser_type",
      "mcp__plugin_playwright_playwright__browser_fill_form",
      "mcp__plugin_playwright_playwright__browser_press_key",
      "mcp__plugin_playwright_playwright__browser_hover",
      "mcp__plugin_playwright_playwright__browser_select_option",
      "mcp__plugin_playwright_playwright__browser_drag",
      "mcp__plugin_playwright_playwright__browser_file_upload",
      "mcp__plugin_playwright_playwright__browser_evaluate",
      "mcp__plugin_playwright_playwright__browser_run_code",
      "mcp__plugin_playwright_playwright__browser_handle_dialog",
      "mcp__plugin_playwright_playwright__browser_resize",
      "mcp__plugin_playwright_playwright__browser_close",
      "mcp__plugin_playwright_playwright__browser_install",
      "mcp__plugin_playwright_playwright__browser_wait_for",
      "mcp__plugin_playwright_playwright__browser_tabs",

      "// --- Git (write operations) ---",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git push *)",
      "Bash(git pull *)",
      "Bash(git merge *)",
      "Bash(git rebase *)",
      "Bash(git checkout *)",
      "Bash(git switch *)",
      "Bash(git stash *)",
      "Bash(git cherry-pick *)",
      "Bash(git fetch *)",

      "// --- Node.js (install / modify deps) ---",
      "Bash(npm install *)",
      "Bash(npm ci)",
      "Bash(npm ci *)",
      "Bash(npm uninstall *)",
      "Bash(yarn install *)",
      "Bash(yarn add *)",
      "Bash(yarn remove *)",
      "Bash(pnpm install *)",
      "Bash(pnpm add *)",
      "Bash(pnpm remove *)",
      "Bash(bun install *)",
      "Bash(bun add *)",
      "Bash(bun remove *)",

      "// --- Python (install / modify deps) ---",
      "Bash(pip install *)",
      "Bash(pip uninstall *)",
      "Bash(pip3 install *)",
      "Bash(pip3 uninstall *)",
      "Bash(poetry install *)",
      "Bash(poetry add *)",
      "Bash(poetry remove *)",
      "Bash(poetry lock *)",
      "Bash(uv pip install *)",
      "Bash(uv add *)",

      "// --- Rust (modify deps) ---",
      "Bash(cargo add *)",
      "Bash(cargo remove *)",
      "Bash(cargo install *)",
      "Bash(cargo update *)",

      "// --- Go (modify deps) ---",
      "Bash(go mod *)",
      "Bash(go get *)",
      "Bash(go install *)",

      "// --- Docker (lifecycle) ---",
      "Bash(docker build *)",
      "Bash(docker run *)",
      "Bash(docker exec *)",
      "Bash(docker stop *)",
      "Bash(docker start *)",
      "Bash(docker restart *)",
      "Bash(docker compose up *)",
      "Bash(docker compose down *)",
      "Bash(docker compose restart *)",
      "Bash(docker compose build *)",

      "// --- GitHub CLI (write) ---",
      "Bash(gh pr create *)",
      "Bash(gh pr merge *)",
      "Bash(gh pr close *)",
      "Bash(gh pr review *)",
      "Bash(gh issue create *)",
      "Bash(gh issue close *)",
      "Bash(gh repo create *)"
    ],

    "deny": [
      "// --- File system destruction ---",
      "Bash(rm -rf *)",
      "Bash(rm -r *)",

      "// --- Privilege escalation ---",
      "Bash(* sudo *)",
      "Bash(sudo *)",
      "Bash(su *)",
      "Bash(runas *)",

      "// --- Disk / filesystem destruction ---",
      "Bash(dd *)",
      "Bash(mkfs *)",
      "Bash(fdisk *)",
      "Bash(format *)",

      "// --- Permission abuse ---",
      "Bash(chmod 777 *)",
      "Bash(chmod -R 777 *)",

      "// --- Git destructive ---",
      "Bash(git push --force *)",
      "Bash(git push -f *)",
      "Bash(git reset --hard *)",
      "Bash(git clean -f *)",
      "Bash(git clean -fd *)",
      "Bash(git clean -fx *)",

      "// --- Docker destructive ---",
      "Bash(docker system prune *)",
      "Bash(docker volume prune *)",
      "Bash(docker image prune *)",

      "// --- Sensitive file access ---",
      "Read(./**/.env)",
      "Read(./**/.env.local)",
      "Read(./**/.env.*.local)",
      "Read(./**/secrets/**)",
      "Read(~/.ssh/**)",
      "Read(~/.aws/**)",
      "Read(~/.kube/**)",
      "Read(~/.config/gcloud/**)",
      "Read(~/.azure/**)",
      "Read(./**/*credentials*)",
      "Read(./**/*.pem)",
      "Read(./**/*.key)",
      "Read(./**/*.p12)",
      "Read(./**/*.pfx)",
      "Read(./**/.htpasswd)",
      "Read(~/.netrc)"
    ]
  }
}
```

**Important:** JSON does not support comments. The `"// --- ... ---"` strings
above are for documentation purposes in this reference only. The actual
generated `settings.json` must omit them (or the skill can strip them during
generation).

---

## Sources

### Claude Code Permissions & Security
- [Configure permissions — Claude Code Docs](https://code.claude.com/docs/en/permissions)
- [Security — Claude Code Docs](https://code.claude.com/docs/en/security)
- [Claude Code Security Best Practices — Backslash](https://www.backslash.security/blog/claude-code-security-best-practices)
- [Claude Code Sandboxing — Anthropic Engineering](https://www.anthropic.com/engineering/claude-code-sandboxing)
- [Better Claude Code Permissions — Korny's Blog](https://blog.korny.info/2025/10/10/better-claude-code-permissions)
- [Claude Code Permissions: Safe vs Fast — claudefa.st](https://claudefa.st/blog/guide/development/permission-management)
- [Claude Code --dangerously-skip-permissions Guide](https://www.ksred.com/claude-code-dangerously-skip-permissions-when-to-use-it-and-when-you-absolutely-shouldnt/)
- [Permissions and Security in Claude Code — angelo-lima.fr](https://angelo-lima.fr/en/claude-code-permissions-security/)
- [Claude Code managed-settings.json Guide](https://managed-settings.com/)
- [Claude Code Settings Reference — claudefa.st](https://claudefa.st/blog/guide/settings-reference)
- [Pwning Claude Code in 8 Ways — Flatt Security](https://flatt.tech/research/posts/pwning-claude-code-in-8-different-ways/)
- [Claude Code Security — MintMCP](https://www.mintmcp.com/blog/claude-code-security)
- [Claude Code Example Settings — GitHub](https://github.com/anthropics/claude-code/tree/main/examples/settings)

### MCP Server Tools
- [GitHub MCP Server — github/github-mcp-server](https://github.com/github/github-mcp-server)
- [GitHub MCP Server Configuration](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md)
- [Playwright MCP Server — microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)
- [Playwright MCP Supported Tools](https://executeautomation.github.io/mcp-playwright/docs/playwright-web/Supported-Tools)
- [Context7 MCP Server — upstash/context7](https://github.com/upstash/context7)
- [Securing MCP Servers — InfraCloud](https://www.infracloud.io/blogs/securing-mcp-servers/)

### Dangerous Commands & Security
- [8 Risky Commands in Unix — Proofpoint](https://www.proofpoint.com/us/blog/insider-threat-management/8-risky-commands-unix)
- [14 Dangerous Linux Terminal Commands — PhoenixNAP](https://phoenixnap.com/kb/dangerous-linux-terminal-commands)
- [MCP Wildcard Permissions Issue #2928](https://github.com/anthropics/claude-code/issues/2928)
- [Sub-agents Bypass Deny Rules Issue #25000](https://github.com/anthropics/claude-code/issues/25000)
