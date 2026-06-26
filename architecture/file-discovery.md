# File discovery

Which files the tool visits, and which it skips, when handed a directory.

## Input

The CLI takes a single directory path. A path that is not a directory is a
usage error (argparse `parser.error`, exit 2) — the tool never operates on a
lone file argument.

## Ignore rules

Traversal is driven by `pathspec.GitIgnoreSpec`, i.e. real `.gitignore`
semantics. The ignore set is built from:

- A fixed baseline: `.git`, `.cache`, `.uv-cache` (the last two are uv's
  caches, which would otherwise be walked).
- The directory's own `.gitignore`, if present — its lines are appended to the
  baseline.

`match_tree_files(path, negate=True)` then yields the files **not** ignored.
The spec is loaded once and applied to the whole tree.

## Path resolution

`match_tree_files` yields paths **relative to the scanned directory**, not the
caller's working directory. Each is rejoined to the input path (`path /
filename`) before opening, so the tool behaves the same regardless of where it
is invoked from.

## Open mode

Files are opened in binary: `rb` in check mode (read-only, no accidental
writes) and `rb+` in fix mode (in-place read/write). Binary mode is what lets
[EOF normalization](eof-normalization.md) reason about exact terminator bytes
and seek from the end without newline translation.
