# Architecture

The living truth home: what `eof-fixer` does **now**. One file per capability,
living prose, no frontmatter — dated by git.

**Promotion rule:** when a change alters a capability's behavior, hand-edit the
matching `architecture/<capability>.md` in the **same PR** that ships the code.
The edit rides in the implementing diff and is reviewed with it — never applied
as a separate post-merge step. The change bundle in `planning/changes/` stays as
the *why*; these files are the *what is true now*.

## Capabilities

- [`eof-normalization.md`](eof-normalization.md) — the core: binary skip, the
  none/append_lf/truncate action model, terminator handling, in-place mutation.
- [`file-discovery.md`](file-discovery.md) — directory input, `.gitignore`
  rules, path resolution, open modes.
- [`cli.md`](cli.md) — command-line interface, output, and exit-code contract.
