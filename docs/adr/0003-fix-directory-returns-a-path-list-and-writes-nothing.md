# `fix_directory` returns a path list and writes nothing

`fix_directory` returns `list[pathlib.Path]` in walk order and touches no stream; `main()` renders
the `Fixing <path>` lines and derives the 0/1 exit code from that list after the walk returns. A
`FixReport` carrying counts and categories was rejected because the only two consumers, the
rendered lines and the exit code, are satisfied by the bare list, and streaming during the walk was
rejected because it means handing `fix_directory` a stream or a callback and re-fusing the I/O the
module was extracted to separate. Only the timing of the report changes, which costs nothing for a
gate over a pruned tree, and the I/O-free module is what lets the content-level tests run against
`BytesIO`. `main()` writes with an explicit `sys.stdout.write` and `\n` rather than `print()`,
keeping stream and terminator visible at the call site, and the skip names it passes down are
module constants, not settings: no config file or `[tool.eof-fixer]` section, only the repeatable
`--exclude` flag.
