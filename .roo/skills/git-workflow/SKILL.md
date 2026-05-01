---
name: git-workflow
description: Check git state, review changes, commit in logical groups, run tests, and push to origin with SSH agent setup for GitLab.
---

# Git Workflow Skill

A reusable skill for checking git state, reviewing changes, committing in logical groups, running tests, and pushing to origin.

## Prerequisites

- SSH key at `~/.ssh/gitlab`
- The project uses `uv` for execution

## Workflow Steps

### 1. Start SSH Agent & Add Key

SSH agent does not persist across terminal sessions. Always combine agent setup with the git command in one shell invocation:

```bash
eval $(ssh-agent) && ssh-add ~/.ssh/gitlab && <git-command>
```

### 2. Check Local Git State

```bash
# Full status (modified + untracked)
git status

# Branches (local + remote)
git branch -a

# Recent commit log
git log --oneline -20

# Remote configuration
git remote -v
```

### 3. Fetch from Origin & Compare

```bash
# Fetch (with SSH agent)
eval $(ssh-agent) && ssh-add ~/.ssh/gitlab && git fetch origin

# Check ahead/behind counts
git rev-list --left-right --count origin/main...main

# List commits local-only (not on origin)
git log origin/main..main --oneline

# List commits on origin-only (not local)
git log main..origin/main --oneline
```

### 4. Review Changes Before Committing

```bash
# Summary of changes (files + insertions/deletions)
git diff --stat

# Full diff for specific areas
git diff <path-or-file>

# Check staged vs unstaged
git diff --cached --stat
```

### 5. Commit in Logical Groups

Group related changes into atomic commits. Each commit should:

- Be a single logical change (refactor, feature, fix, docs, tests, build)
- Have a descriptive message following conventional commits format:
  `<type>(<scope>): <description>`
- Pass tests independently

**Commit message format:**
```
<type>(<scope>): <short description>

<optional body with details>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `build`, `perf`, `chore`

**Example workflow for multiple commits:**
```bash
# Commit 1: CLI refactoring
git add main.py cli/setup.py cli/*_commands.py
git commit -m "refactor(cli): extract inline typer commands into modular CLI files"

# Commit 2: Core changes
git add core/ indexer/ cli/run_indexer.py
git commit -m "refactor(core): lazy client singletons, shared language defs"

# Commit 3: Feature changes
git add scout/
git commit -m "feat(scout): batch crawling, rate limiting, concurrency"

# Commit 4: Build/deps
git add pyproject.toml uv.lock install.sh setup.sh
git commit -m "build: move crawl4ai/playwright to scout extras"

# Commit 5: Server changes
git add server/
git commit -m "feat(server): improve MCP tools, API metrics"

# Commit 6: Tests
git add tests/
git commit -m "test: update mocks, add integration tests"

# Commit 7: Docs
git add AGENTS.md README.md docs/
git commit -m "docs: add agent workflow rules, MCP API reference"
```

### 6. Run Tests Before Pushing

Always run the full test suite before pushing:

```bash
uv run pytest
```

If the change is scoped, run targeted tests first for faster feedback, but the full suite must pass before final submission.

### 7. Push to Origin

```bash
eval $(ssh-agent) && ssh-add ~/.ssh/gitlab && git push origin main
```

### 8. Verify Final State

```bash
# Confirm working tree is clean
git status --short

# Review the commit log
git log --oneline -10
```

## Key Lessons from Practice

1. **SSH agent is ephemeral** — always combine `eval $(ssh-agent) && ssh-add` with the actual git command in one shell invocation. Separate terminal sessions lose the agent.
2. **Review before commit** — use `git diff --stat` first to understand the scope, then `git diff <path>` for detailed review.
3. **Atomic commits** — group by concern (refactor, feature, build, test, docs), not by file location. Each commit should be a single logical change.
4. **Test before push** — `uv run pytest` must pass. This is non-negotiable.
5. **Working tree should be clean** after all commits. If there are remaining unstaged files, assess whether they belong to the current batch or are intentional leftovers.
6. **Avoid backticks in commit message bodies** — when using `git commit -m`, the shell interprets backtick-enclosed text as command substitution. Use plain text or single quotes in commit message bodies. For multi-line messages, prefer `git commit` without `-m` to open an editor, or use `-m` with plain text only.
