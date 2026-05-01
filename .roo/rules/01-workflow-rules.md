# Hivemind Workflow Rules

These rules apply to all AI agents working on this repository.

## Project Execution

The project is managed exclusively via **uv**. Do not use `python` or `pip` directly — they are not guaranteed to be available on the path.

- Always use `uv run <script>` to execute any module or script.
- Use `uv add <package>` to add new dependencies.
- Use `uv sync` to install the project and its dependencies (equivalent to `pip install`).
- Use `uv lock` to update the lockfile after changes to `pyproject.toml`.

## Test Before Completion

- Before submitting any change or marking a task as **done**, you **must** run the full test suite:

  ```bash
  uv run pytest
  ```

- If the change is scoped to a specific area, you may additionally run targeted tests first for faster feedback, but the full suite must pass before final submission.

## Documentation Must Stay In Sync

- Whenever you modify code, update the relevant documentation in `/docs/` to reflect the changes.
- Keep `README.md` up to date if the change affects onboarding, configuration, or usage.
- Outdated documentation is considered a bug.

## Prefer Semantic Search Over File Search

- When exploring the codebase to understand how something works or where to make changes, **always use semantic search first** (via `codebase_search` tool) rather than grepping for literal strings or manually navigating directories.
- Semantic search finds relevant code based on meaning, which is far more effective than regex-based search for understanding implementations.
- Fall back to regex/file search only when semantic search does not yield useful results.
