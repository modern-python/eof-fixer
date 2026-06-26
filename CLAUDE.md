# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

See `Justfile` for recipes (`just --list`). Notes that aren't obvious from the recipes:

- `just lint` auto-fixes; `just lint-ci` is check-only (used in CI).
- `just test` runs `uv run --no-sync pytest` with coverage always enabled; it
  forwards args, e.g. `just test tests/test_end_of_file_fixer.py::test_name`.

## Planning

This repo follows the two-axis planning convention — see
[`planning/README.md`](planning/README.md). Start with its **Quick path** to
pick a lane (Full / Lightweight / Tiny) before making a change.

When a change alters capability behavior, update the matching
`architecture/<capability>.md` in the same PR.

## Architecture

Single-purpose CLI tool: ensures text files end with exactly one newline.

- **Entry point:** `eof_fixer/main.py:main()` — requires a directory path arg, loads `.gitignore` via `pathspec.GitIgnoreSpec`, iterates non-ignored files (opened `rb` in check mode, `rb+` otherwise), calls `_fix_file()` on each
- **`_fix_file(file_obj, check)`** — skips binary files (null bytes in first 1024 bytes), then delegates to `_detect_trailing()`, which returns the action: `none` (empty or already ends with one terminator), `append_lf` (no trailing newline → add `\n`), or `truncate` (all-newlines → truncate to empty, or excess trailing newlines → truncate to one)
- **Check mode (`--check`)** — reports what would change without writing; exit code 1 if any files need fixing

Files skipped: binary files, empty files, `.git`/`.cache`/`.uv-cache` directories, and anything matched by the directory's `.gitignore`.

## Tooling

- **uv** for dependency management and running scripts
- **ruff** for formatting and linting (line length 120)
- **ty** for type checking (use `ty: ignore` for suppressions, not `# type: ignore`)
- **pytest** with `pytest-cov` for testing; fixtures in `tests/fixtures/`

## Conventions

- No `print()` in library/CLI source — it's a code smell here. Use
  `sys.stdout.write(...)` / `sys.stderr.write(...)` with an explicit `\n` in the
  format string. When fixing output bugs, amend the existing `write` call (add
  `\n`, change destination) rather than swapping in `print()`. `print()` is fine
  in tests, scratch scripts, and REPL examples.
