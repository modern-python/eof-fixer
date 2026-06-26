# CLI

The command-line surface and its contract with callers (shells, CI, pre-commit).

## Interface

- `eof-fixer <path>` — fix every non-ignored text file under `<path>` in place.
- `eof-fixer <path> --check` — report what would change, write nothing.
- `eof-fixer <path> --exclude DIR` — add `DIR` to the set of names skipped
  during traversal. The flag is **repeatable** (`--exclude node_modules
  --exclude dist`). It augments the always-skipped `.git` and the defaults
  `.cache` / `.uv-cache`; `.git` is not configurable and cannot be removed
  from the skip set.

`<path>` is required and must be a directory; otherwise argparse exits 2 with a
usage error. See [file-discovery](file-discovery.md) for what counts as a
visited file.

## Output

For each file that needs (or would need) fixing, the tool writes `Fixing
<filename>\n` to stdout — the relative path as discovery yielded it. Output goes
through `sys.stdout.write`, not `print`.

## Exit code

`main()` accumulates a result by OR-ing each file's outcome:

- **0** — every file already ended correctly (nothing changed / nothing would
  change).
- **1** — at least one file needed fixing. In fix mode it was fixed; in
  `--check` mode it was only flagged.

This makes `--check` a CI/pre-commit gate: exit 1 signals "files are
non-conforming" without mutating the tree.
