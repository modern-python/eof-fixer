# eof-fixer

A CLI that walks a directory tree, honoring nested `.gitignore` files, and rewrites every text file
it visits to end with exactly one line terminator.

## Language

A term is listed only when there is a synonym to reject, or a meaning subtle enough that code and
docs must agree on it. General programming vocabulary does not belong here, however heavily this tool
uses it.

**Terminator**:
The byte sequence that ends a line: `\n`, `\r\n`, or `\r`. "Exactly one terminator" is counted in
sequences, not bytes: a file ending in a single `\r\n` is already correct. The tool normalizes the
*count* and preserves the *style*, with one exception: a file that ends in no terminator at all gets
an LF, whatever the rest of it uses.

**Fixed**:
What `fix_file` and `fix_directory` report. Under `--check` nothing is written, yet the same paths
come back; "fixed" there means *would be*. The exit code is derived from the same list either way.

**Check mode**:
The `--check` run: decide and report, write nothing.
_Avoid_: dry run.

**Ignored**:
Matched by a `.gitignore` rule in the spec stack. The verdict comes from the deepest spec that
returns one, so a negation re-includes.
_Avoid_: excluded.

**Excluded**:
A bare name given to `--exclude`, or one of `DEFAULT_EXCLUDES`. Excludes are compiled into a single
baseline spec anchored at the scanned root and evaluated *beneath* every real `.gitignore`, so an
in-tree negation outranks them. `.git` is not an exclude: it is pruned by name before any spec is
consulted and cannot be re-included.
_Avoid_: ignored.
