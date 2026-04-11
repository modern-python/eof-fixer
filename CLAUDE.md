# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
just install        # Lock deps and sync
just lint           # Format + check + type check (auto-fixes)
just lint-ci        # Lint in check mode only (no fixes)
just test           # Run pytest with coverage
just test tests/test_end_of_file_fixer.py::test_name  # Run a single test
```

Tests use `uv run --no-sync pytest` under the hood. Coverage is always enabled.

## Architecture

Single-purpose CLI tool: ensures text files end with exactly one newline.

- **Entry point:** `eof_fixer/main.py:main()` — parses args, loads `.gitignore` via `pathspec.GitIgnoreSpec`, iterates non-ignored files, calls `_fix_file()` on each
- **`_fix_file(file_obj, check)`** — opens files in binary `rb+` mode, detects binary files (null bytes in first 1024 bytes), handles four cases: empty file (skip), no trailing newline (add `\n`), all-newlines file (truncate to empty), multiple trailing newlines (truncate to one)
- **Check mode (`--check`)** — reports what would change without writing; exit code 1 if any files need fixing

Files skipped: binary files, empty files, `.git`/`.cache`/`.uv-cache` directories, and anything matched by the directory's `.gitignore`.

## Tooling

- **uv** for dependency management and running scripts
- **ruff** for formatting and linting (line length 120)
- **ty** for type checking (use `ty: ignore` for suppressions, not `# type: ignore`)
- **pytest** with `pytest-cov` for testing; fixtures in `tests/fixtures/`
