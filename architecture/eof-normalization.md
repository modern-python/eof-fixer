# EOF normalization

The core capability: given a single open file, decide whether its end-of-file
terminator is correct and, in fix mode, make it so. "Correct" means the file
ends with **exactly one** line terminator — no missing newline, no trailing
blank lines.

## Binary skip

Before inspecting terminators, the file is sampled: the first 1024 bytes are
read and if any contain a null byte (`\x00`), the file is treated as binary and
left untouched. The sample read restores the original stream position, so
detection is side-effect-free. This is a heuristic, not a content-type sniff —
text files never contain null bytes; most binary formats do within the first
kilobyte.

## The action model

Inspection returns one of three actions, derived purely from the file's tail:

- **`none`** — nothing to do. The file is empty (a seek to the last byte
  fails), or it already ends with exactly one terminator.
- **`append_lf`** — the last byte is not a terminator, so a single `\n` is
  appended.
- **`truncate(offset)`** — there are excess trailing terminators; the file is
  cut to `offset`. `offset == 0` means the file is **all** terminators and is
  truncated to empty.

This split keeps the *decision* (read-only, used by check mode) separate from
the *mutation* (write mode), so the same logic drives both modes.

## Terminator handling

Detection walks backwards from the last byte over the run of `\n`/`\r`
characters to find where real content ends. The first terminator sequence
immediately after that content determines what "exactly one terminator" means
for this file — checked in order `\n`, `\r\n`, `\r`. So a file ending in one
`\r\n` is already correct and left alone, while one ending in `\r\n\r\n` is
truncated back to a single `\r\n`. Mixed and legacy line endings are respected:
the existing terminator style is preserved, only the *count* is normalized.

## Mutation

In fix mode:

- `append_lf` seeks to end-of-file before writing the `\n`. The explicit seek
  is required on Windows, where a read-then-write on a `rb+` stream otherwise
  raises.
- `truncate` seeks to the computed offset and truncates there.

In check mode no bytes are written; the action is computed and reported only.

Either way, a file that needed changing contributes a non-zero result to the
caller — see [cli](cli.md) for how that becomes the process exit code and the
`Fixing <file>` line.
