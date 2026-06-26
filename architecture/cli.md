# CLI

The command-line surface and its contract with callers (shells, CI, pre-commit).

`main()` is a thin adapter over `fix_directory`: it parses args, guards
`is_dir` (exit 2), delegates the walk to `fix_directory`, renders one
`Fixing <path>` line per returned path, and exits `1`/`0`. It holds no
file-level logic. See [eof-normalization](eof-normalization.md) for how
`fix_directory` and `fix_file` do the actual work.

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
<filename>\n` to stdout — the relative path as discovery yielded it. Output
goes through `sys.stdout.write`, not `print`. Output is batch-rendered:
all `Fixing` lines are written after `fix_directory` returns, not streamed
during the walk.

## Exit code

`main()` derives its result from the list returned by `fix_directory`:

- **0** — every file already ended correctly (nothing changed / nothing would
  change).
- **1** — at least one file needed fixing. In fix mode it was fixed; in
  `--check` mode it was only flagged.

This makes `--check` a CI/pre-commit gate: exit 1 signals "files are
non-conforming" without mutating the tree.
