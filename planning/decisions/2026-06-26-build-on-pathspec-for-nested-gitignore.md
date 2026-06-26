---
status: accepted
summary: Build nested .gitignore resolution on the existing pathspec dependency rather than adopt a dedicated library.
---

# Build nested .gitignore on pathspec, not a dedicated library

**Decision:** Implement nested `.gitignore` resolution as a small walk over
`pathspec.GitIgnoreSpec`, rather than adding a nested-gitignore library
(e.g. `igittigitt`).

## Context

Honoring nested `.gitignore` needs per-directory rule collection plus correct
precedence. Dedicated libraries (`igittigitt`, `gitignorefile`,
`gitignore_parser`) offer recursive collection out of the box. `pathspec` is
already the sole runtime dependency and matches a single flat spec only.

## Decision & rationale

`pathspec` is the most actively maintained option (2026 releases vs. 2024/2022
for the alternatives) and its matching engine most rigorously replicates git,
including edge cases the alternatives get wrong — `igittigitt`'s own README
documents a cross-directory negation case that fails. A dedicated library would
add a second, less-maintained pattern engine and pull in the global git ignore
by default, in exchange for saving only ~30 lines of directory-collection code
that we cover with a small, well-tested walk. Keeping one engine preserves the
tool's minimal-dependency footprint and its best-available correctness.

## Revisit trigger

Reopen if the per-directory walk accumulates real complexity (e.g. we need
`.git/info/exclude`, global excludes, or true "tracked-files-win" semantics),
at which point shelling out to git or adopting a maintained library may win.
