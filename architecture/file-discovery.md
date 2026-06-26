# File discovery

Which files the tool visits, and which it skips, when handed a directory.

## Input

The CLI takes a single directory path. A path that is not a directory is a
usage error (argparse `parser.error`, exit 2) — the tool never operates on a
lone file argument.

## Ignore rules

Discovery lives in `eof_fixer/discovery.py` as `iter_text_files(root,
extra_excludes)`; `main()` calls it and iterates the results.

The walk is a **top-down DFS** that carries a stack of per-directory
`GitIgnoreSpec`s — one spec per `.gitignore` encountered, anchored at the
directory it lives in. Each entry is classified by evaluating the stack
**deepest-first**: the first spec that returns a definitive
`check_file().include` verdict wins (git precedence: closest `.gitignore`
wins, last match within a file wins, negation re-includes).

At the bottom of the stack sits a **baseline spec** built from `.cache`,
`.uv-cache`, and any names passed via `--exclude` — anchored at the scanned
root and evaluated beneath every directory's `.gitignore`. This ensures
today's default skip behaviour is preserved even in trees that carry no
`.gitignore` at all.

Additional rules applied unconditionally:

- **`.git` directories** are pruned by name — hard-skipped before any spec is
  evaluated, never configurable.
- **Ignored directories** are pruned rather than descended (git-correct: git
  forbids re-including a file whose parent directory is excluded, so pruning
  loses no reachable files).
- **Symlinks** are skipped — symlinked directories are not followed, avoiding
  loops.

The implementation is **pure-filesystem**: it reads only on-disk `.gitignore`
files and never invokes git. It does not consult `.git/info/exclude`,
`core.excludesFile`, or any other git-state source, so it works correctly on
any directory, not just git repositories.

## Path resolution

`iter_text_files` yields paths **relative to the scanned root**, not the
caller's working directory. Each is rejoined to the root path (`root /
rel_path`) before opening, so the tool behaves the same regardless of where
it is invoked from.

## Open mode

Files are opened in binary: `rb` in check mode (read-only, no accidental
writes) and `rb+` in fix mode (in-place read/write). Binary mode is what lets
[EOF normalization](eof-normalization.md) reason about exact terminator bytes
and seek from the end without newline translation.
