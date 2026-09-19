# Build nested `.gitignore` on pathspec, not a dedicated library

Honoring nested `.gitignore` files needs per-directory rule collection and git's precedence, which
`igittigitt`, `gitignorefile` and `gitignore_parser` all provide out of the box while `pathspec`
matches one flat spec at a time. `discovery.py` builds the stack itself, a short walk that pushes
and pops a `pathspec.GitIgnoreSpec` per directory and takes the deepest definitive verdict, because
`pathspec` is already the sole runtime dependency, is the most actively maintained of the four, and
reproduces git's matching most closely, including the cross-directory negation case `igittigitt`'s
own README documents as failing. A dedicated library would add a second, less maintained pattern
engine and read the user's global git ignore by default, breaking the promise that ignore rules come
only from `.gitignore` files inside the scanned tree, repository or not, which
`tests/test_discovery.py` pins as an invariant. Needing `.git/info/exclude`, global excludes or true
tracked-files-win semantics is what would reopen this in favour of shelling out to git.
