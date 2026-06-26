# Type the EOF-Action Seam — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stringly-typed EOF-action seam in `eof_fixer/fixer.py` with a sealed union of frozen dataclasses (`Noop | AppendLf | Truncate`) consumed by an exhaustive `match`. Behavior unchanged.

**Architecture:** `_detect_trailing` returns `_EofAction` instead of `tuple[str, int]`; `fix_file` consumes it with a wildcard-free `match`. ty enforces exhaustiveness via `fix_file`'s `bool` return type (an unhandled future variant ⇒ implicit-`None` return error) — no `assert_never`, no new pragmas, 3.10-safe.

**Tech Stack:** Python 3.10+ (`match`, PEP 604 unions, `dataclasses`), ty, pytest (100% coverage enforced).

## Global Constraints

- Python `>=3.10,<4`; `target-version = py310`. No 3.11+ APIs (`typing.assert_never`/`typing.Never` are out).
- Runtime dependencies: `pathspec` only — add none.
- All imports at module level (incl. tests). `ty: ignore` not `# type: ignore`. No `print()` in source. Annotate test args. ruff `select = ["ALL"]`, line length 120, `D1` ignored (docstrings optional).
- 100% coverage enforced by `just test`.
- Behavior must not change: same `fix_file`/`fix_directory` signatures and results; the public CLI is untouched.
- Conventional-commit messages ending with:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- Full-lane change: the implementing work updates `architecture/eof-normalization.md` (Task 2).

---

### Task 1: Replace the seam with a sealed union in `fixer.py`

**Files:**
- Modify: `eof_fixer/fixer.py` (add the dataclasses + alias; retype `_detect_trailing`; rewrite `fix_file`'s consumption)
- Modify: `tests/test_fixer.py` (add one coverage test for the `Truncate`-under-`--check` branch)

**Interfaces:**
- Internal (new, not exported): `Noop`, `AppendLf`, `Truncate(offset: int)`, `_EofAction = Noop | AppendLf | Truncate`.
- Unchanged public: `fix_file(file_obj, *, check) -> bool`, `fix_directory(...) -> list[pathlib.Path]`.

- [ ] **Step 1: Add the coverage test for the truncate check-mode branch**

In `tests/test_fixer.py`, add (next to the other `_run`-based content tests; it reuses the existing `_run` helper):

```python
def test_check_mode_truncate_does_not_write() -> None:
    assert _run(b"abc\n\n\n", check=True) == (True, b"abc\n\n\n")
```

- [ ] **Step 2: Run it — it passes on the current code**

Run: `just test tests/test_fixer.py::test_check_mode_truncate_does_not_write`
Expected: PASS. (This is a coverage-completeness test, not a red-green test — the current single `if not check:` already takes this path; after the refactor splits that guard per case, this test keeps the `Truncate` check-branch covered.)

- [ ] **Step 3: Refactor `eof_fixer/fixer.py`**

Add `import dataclasses` to the import block (keep `os`, `pathlib`, `Iterator`/`Sequence`, `IO`, and the `iter_text_files` import). Replace the `_detect_trailing` definition and the `fix_file` body as follows; leave `_is_binary`, `DEFAULT_EXCLUDES`, `_BINARY_SAMPLE_SIZE`, and `fix_directory` exactly as they are.

Add the action types just below the constants:

```python
@dataclasses.dataclass(frozen=True)
class Noop:
    """No change: the file is empty or already ends with exactly one terminator."""


@dataclasses.dataclass(frozen=True)
class AppendLf:
    """The file lacks a trailing newline; append a single LF."""


@dataclasses.dataclass(frozen=True)
class Truncate:
    """The file has excess trailing newlines; truncate to `offset` (0 = empty)."""

    offset: int


_EofAction = Noop | AppendLf | Truncate
```

Replace `_detect_trailing` with:

```python
def _detect_trailing(file_obj: IO[bytes]) -> _EofAction:
    """Inspect the end of `file_obj` and return the action needed."""
    try:
        file_obj.seek(-1, os.SEEK_END)
    except OSError:
        return Noop()

    last_character = file_obj.read(1)
    if not last_character:
        return Noop()
    if last_character not in {b"\n", b"\r"}:
        return AppendLf()

    while last_character in {b"\n", b"\r"}:
        if file_obj.tell() == 1:
            # All bytes are line terminators — truncate to empty.
            return Truncate(0)
        file_obj.seek(-2, os.SEEK_CUR)
        last_character = file_obj.read(1)

    position = file_obj.tell()
    remaining = file_obj.read()
    for sequence in (b"\n", b"\r\n", b"\r"):
        if remaining == sequence:
            return Noop()
        if remaining.startswith(sequence):
            return Truncate(position + len(sequence))

    raise AssertionError("unreachable")  # pragma: no cover  # noqa: EM101
```

Replace `fix_file` with:

```python
def fix_file(file_obj: IO[bytes], *, check: bool) -> bool:
    """Normalize one open binary file to end with exactly one terminator.

    Returns True if the file was fixed (or, under `check`, would be fixed).
    Binary files (null byte in the first sample) are skipped, returning False.
    """
    if _is_binary(file_obj):
        return False

    match _detect_trailing(file_obj):
        case Noop():
            return False
        case AppendLf():
            if not check:
                # Needs this seek for windows, otherwise IOError
                file_obj.seek(0, os.SEEK_END)
                file_obj.write(b"\n")
            return True
        case Truncate(offset):
            if not check:
                file_obj.seek(offset)
                file_obj.truncate()
            return True
```

(No `case _`: the three cases cover `_EofAction`, and ty enforces exhaustiveness through the `-> bool` return type.)

- [ ] **Step 4: Run the full suite + coverage**

Run: `just test`
Expected: PASS — all existing `test_fixer.py` / `test_end_of_file_fixer.py` tests stay green (behavior is identical), plus the new truncate check-mode test. Coverage 100% (the per-case `if not check:` branches are all exercised: append-non-check, append-check, truncate-non-check, truncate-check).

- [ ] **Step 5: Confirm the exhaustiveness guard is live (manual, not committed)**

Temporarily add a dummy variant to the union (e.g. `class _Probe: ...` and `_EofAction = Noop | AppendLf | Truncate | _Probe`) and run `just lint-ci`; confirm ty reports `invalid-return-type` on `fix_file`. Then revert the probe. Record the observed error text in your report. (This proves the seam is exhaustively checked; do not commit the probe.)

- [ ] **Step 6: Lint**

Run: `just lint`, then confirm a clean `just lint-ci` against the committed tree.

- [ ] **Step 7: Commit**

```bash
git add eof_fixer/fixer.py tests/test_fixer.py
git commit -m "refactor: type the EOF-action seam with a sealed union

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Promote to architecture + finalize the bundle summary

**Files:**
- Modify: `architecture/eof-normalization.md`
- Modify: `planning/changes/2026-06-26.03-type-eof-action-seam/design.md` (finalize `summary`)

**Interfaces:** Documentation only.

- [ ] **Step 1: Update `architecture/eof-normalization.md`**

Read the file first. Its "action model" section describes the three actions as
the strings `none` / `append_lf` / `truncate`. Reword it to describe the typed
sealed union: `_detect_trailing` returns `_EofAction = Noop | AppendLf | Truncate(offset)`
(a frozen-dataclass sum type, offset only on `Truncate`), and `fix_file`
consumes it with an exhaustive `match` whose completeness ty enforces via the
`bool` return type. Preserve the surrounding terminator / binary-skip prose;
only the action-model description changes.

- [ ] **Step 2: Finalize the bundle summary**

In `planning/changes/2026-06-26.03-type-eof-action-seam/design.md`, set the
frontmatter `summary:` to the realized result, e.g.:
`summary: _detect_trailing now returns a sealed union (Noop | AppendLf | Truncate) consumed by an exhaustive match in fix_file; the magic strings and dummy offset are gone, behavior unchanged.`

- [ ] **Step 3: Validate + lint**

Run: `just check-planning` → expect `planning: OK`.
Run: `just lint-ci` → expect clean.

- [ ] **Step 4: Commit**

```bash
git add architecture/eof-normalization.md planning/changes/2026-06-26.03-type-eof-action-seam/design.md
git commit -m "docs: promote the typed EOF-action seam to architecture

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria

- `_detect_trailing -> _EofAction`; `fix_file` consumes via a wildcard-free `match`; the magic strings `"none"`/`"append_lf"`/`"truncate"` and the dummy offset are gone.
- Exhaustiveness is enforced by ty (verified via the Step 5 probe); no `assert_never`, no new pragmas, 3.10-safe.
- Behavior unchanged; `just test` green at 100% coverage; `just lint-ci` clean; `just check-planning` → `planning: OK`.
- `architecture/eof-normalization.md` describes the typed action model; bundle summary finalized.
