---
summary: Respect nested .gitignore files across the whole tree (pure-filesystem, built on pathspec) and add a repeatable --exclude flag.
---

# Design: Respect nested `.gitignore` across the tree

## Summary

Today the tool reads only the **root** `.gitignore` and applies it tree-wide as
a single flat `pathspec.GitIgnoreSpec`. Files ignored by a `.gitignore` in a
subdirectory are still processed. This change makes the file walk honor the
**nested** gitignore convention — per-directory `.gitignore` files with correct
anchoring, precedence, negation, and ignored-directory pruning — while staying
pure-filesystem (no git invocation, works on any directory). It also exposes the
previously-hardcoded extra skip dirs through a repeatable `--exclude` flag.

## Motivation

`main()` builds one `GitIgnoreSpec` from a fixed baseline (`.git`, `.cache`,
`.uv-cache`) plus the root `.gitignore`, then calls `match_tree_files`. A repo
that places `.gitignore` files in subdirectories (the common monorepo / nested
package layout) gets those rules silently ignored, so the tool rewrites files
the user expects git — and therefore the tool — to leave alone. "Respect the
`.gitignore`" is the tool's headline contract; honoring only the root file
breaks it for any non-trivial tree.

## Scope decision

Scope is **nested `.gitignore` files only**. Explicitly out:

- `.git/info/exclude` and global `core.excludesFile` — not read.
- Shelling out to `git check-ignore` / `git ls-files` — not used; the tool must
  keep working on directories that are not git repositories.
- "Tracked files win" — not modeled (it requires git state).

Library decision: build on the existing `pathspec` dependency rather than adopt
a dedicated nested-gitignore library (e.g. `igittigitt`). pathspec is the
most-actively-maintained option, already in the tree, and its matching engine is
the most spec-rigorous; the dedicated libraries would add a second, less-
maintained pattern engine for a saving of only the per-directory collection
code. This is recorded as a decision (`planning/decisions/`) in the implementing
PR.

## Design

### 1. New seam: an ignore-aware file walk

Extract file discovery into a new module `eof_fixer/discovery.py`:

```python
def iter_text_files(root: Path, extra_excludes: Sequence[str]) -> Iterator[Path]:
    """Yield paths (relative to root) of files not ignored by nested .gitignore."""
```

This isolates *which files to visit* (testable on its own, no mutation) from
*fix the file* (the untouched EOF core). `main()` shrinks to: parse args → build
the baseline exclude list → `for rel in iter_text_files(root, excludes): open +
_fix_file`. `_is_binary`, `_detect_trailing`, and `_fix_file` are unchanged.

### 2. Algorithm: top-down DFS with a per-directory spec stack

Descend from `root`, carrying a stack of `(anchor_dir, GitIgnoreSpec)` — each
`.gitignore` parsed once, anchored at the directory it lives in. At the bottom
of the stack sits a **baseline spec** built from the extra-exclude names
(default `.cache`, `.uv-cache`, plus any `--exclude` values), so today's
behavior is preserved.

For each entry, evaluate the stack **deepest → shallowest** and take the first
definitive verdict: `GitIgnoreSpec.check_file(path_relative_to_anchor).include
is not None` (`True` = ignored, `False` = negated/forced-include). This is
exactly git's "closest `.gitignore` wins, last match within a file wins,
negation re-includes" precedence.

- **Directories:** if ignored → prune (do not descend). This is git-correct, not
  merely an optimization: git forbids re-including a file whose parent directory
  is excluded, so pruning loses nothing. If a negation re-includes the directory
  itself, the stack returns "not ignored" and we descend normally.
- **`.git`:** hard-pruned by name, independent of any spec — never un-ignorable.
- **Files:** if not ignored → yield (relative to `root`).
- **Symlinked directories:** not followed, avoiding loops and matching the
  intent of the existing symlink test.

### 3. CLI: `--exclude`

Add a repeatable `--exclude` flag (`action="append"`). `.git` is always skipped
and is **not** configurable. The extra-exclude set is the fixed default
(`.cache`, `.uv-cache`) **augmented** by any `--exclude` values:

- `eof-fixer .` → skip `.git`, `.cache`, `.uv-cache` + all nested `.gitignore`
  rules (backward compatible).
- `eof-fixer . --exclude node_modules --exclude dist` → skip `.git`, `.cache`,
  `.uv-cache`, `node_modules`, `dist` + nested rules.

Output (`Fixing <file>`) and the 0/1 exit-code contract are unchanged.

## Testing

TDD, failing test first. Unit tests drive `iter_text_files` against `tmp_path`
trees:

- A `.gitignore` in a subdirectory ignores files within its subtree.
- A deeper `.gitignore` overrides a shallower rule.
- Negation (`!keep.log`) re-includes a file an ancestor rule ignored.
- An ignored directory is pruned — files inside are never yielded.
- Root-only `.gitignore` behaves exactly as the existing end-to-end test asserts.
- `--exclude` augments the default skip set; `.cache`/`.uv-cache` still skipped.
- `.git` is always skipped.
- A symlink in the tree does not crash the walk.

All existing tests in `tests/test_end_of_file_fixer.py` stay green unchanged.

## Architecture promotion

In the implementing PR, hand-edit:

- `architecture/file-discovery.md` — replace the single-root-`.gitignore`
  description with the nested walk, spec-stack precedence, and pruning.
- `architecture/cli.md` — document the `--exclude` flag.

## Risk

- **pathspec directory-vs-file matching nuance** (directory-only patterns like
  `build/`): mitigated by the test matrix above; resolved concretely during TDD.
- **Performance on large trees:** parsing one spec per directory and walking
  manually is more work than a single `match_tree_files`; acceptable for this
  tool's use, and pruning ignored directories bounds it the same way git does.
- **Behavior change for existing users:** files under a subdirectory
  `.gitignore` that were previously rewritten will now be skipped. This is the
  intended fix and matches user expectation; called out in the release note.
