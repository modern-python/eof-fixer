# Deepen the Fix into `fixer.py` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the EOF-fixing capability into a deep module `eof_fixer/fixer.py` (`fix_file` + `fix_directory`) so `main()` becomes a thin CLI adapter and tests target the interface instead of the `sys.argv`/`sys.stdout`/`os.chdir` harness.

**Architecture:** `fixer.py` owns the file-level helpers (`_is_binary`, `_detect_trailing`), a public `fix_file(file_obj, *, check) -> bool`, and `fix_directory(root, *, check=False, extra_excludes=()) -> list[pathlib.Path]` that drives `discovery.iter_text_files`. `main.py` shrinks to argparse + `is_dir` guard + render + exit. No behavior change except output timing (streaming → batch).

**Tech Stack:** Python 3.10+, `pathspec` (via `discovery`), pytest + pytest-cov (100% enforced).

## Global Constraints

- Python `>=3.10,<4`; no 3.11+-only syntax.
- Runtime dependencies: `pathspec` only — add none.
- All imports at module level, never inside function bodies (including test files).
- Type-checker suppressions use `ty: ignore`, never `# type: ignore`.
- No `print()` in source — output via `sys.stdout.write(...)` with explicit `\n`.
- Annotate test function arguments (e.g. `tmp_path: pathlib.Path`).
- ruff line length 120.
- 100% test coverage is enforced by `just test`; every branch of new code must be covered.
- Conventional-commit messages ending with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- Full-lane planning change: the implementing work hand-edits the matching `architecture/*.md` (Task 3).

---

### Task 1: Create `fixer.py` and rewire `main()` to an adapter

**Files:**
- Create: `eof_fixer/fixer.py`
- Create: `tests/test_fixer.py`
- Modify: `eof_fixer/main.py` (remove `_is_binary`/`_detect_trailing`/`_fix_file`; `main()` calls `fix_directory`)

**Interfaces:**
- Consumes: `eof_fixer.discovery.iter_text_files(root, extra_excludes)`.
- Produces:
  - `fix_file(file_obj: IO[bytes], *, check: bool) -> bool` — True if the file was (or, under `check`, would be) fixed.
  - `fix_directory(root: pathlib.Path, *, check: bool = False, extra_excludes: Sequence[str] = ()) -> list[pathlib.Path]` — relative paths fixed/would-be-fixed, in walk order.
  - `DEFAULT_EXCLUDES = (".cache", ".uv-cache")`.

- [ ] **Step 1: Write the failing tests** (`tests/test_fixer.py`)

```python
import io
import pathlib
import stat

import pytest

from eof_fixer.fixer import fix_directory, fix_file


# ---- content layer: fix_file on BytesIO (no filesystem) ----

def _run(content: bytes, *, check: bool = False) -> tuple[bool, bytes]:
    buffer = io.BytesIO(content)
    changed = fix_file(buffer, check=check)
    return changed, buffer.getvalue()


def test_no_trailing_newline_appends_lf() -> None:
    assert _run(b"abc") == (True, b"abc\n")


def test_single_newline_unchanged() -> None:
    assert _run(b"abc\n") == (False, b"abc\n")


def test_multiple_newlines_truncated_to_one() -> None:
    assert _run(b"abc\n\n\n") == (True, b"abc\n")


def test_newlines_only_truncated_to_empty() -> None:
    assert _run(b"\n\n") == (True, b"")


def test_empty_unchanged() -> None:
    assert _run(b"") == (False, b"")


def test_crlf_no_trailing_appends_lf() -> None:
    assert _run(b"a\r\nb") == (True, b"a\r\nb\n")


def test_crlf_perfect_unchanged() -> None:
    assert _run(b"a\r\nb\r\n") == (False, b"a\r\nb\r\n")


def test_crlf_multiple_truncated_to_one() -> None:
    assert _run(b"a\r\nb\r\n\r\n") == (True, b"a\r\nb\r\n")


def test_cr_only_multiple_truncated_to_one() -> None:
    assert _run(b"a\rb\r\r") == (True, b"a\rb\r")


def test_bom_prefixed_is_treated_as_text() -> None:
    assert _run(b"\xef\xbb\xbfabc") == (True, b"\xef\xbb\xbfabc\n")


def test_null_byte_in_first_1024_is_binary_skipped() -> None:
    assert _run(b"a\x00b") == (False, b"a\x00b")


def test_null_byte_beyond_first_1024_is_treated_as_text() -> None:
    content = b"a" * 1100 + b"\x00data"
    changed, result = _run(content)
    assert changed is True
    assert result == content + b"\n"


def test_check_mode_returns_true_but_does_not_write() -> None:
    assert _run(b"abc", check=True) == (True, b"abc")


# ---- orchestration layer: fix_directory on a temp tree ----

def _names(paths: list[pathlib.Path]) -> set[str]:
    return {str(p) for p in paths}


def test_fixes_files_and_returns_list(tmp_path: pathlib.Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"no nl")
    (tmp_path / "b.txt").write_bytes(b"ok\n")
    fixed = fix_directory(tmp_path)
    assert _names(fixed) == {"a.txt"}
    assert (tmp_path / "a.txt").read_bytes() == b"no nl\n"
    assert (tmp_path / "b.txt").read_bytes() == b"ok\n"


def test_check_mode_writes_nothing(tmp_path: pathlib.Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"no nl")
    fixed = fix_directory(tmp_path, check=True)
    assert _names(fixed) == {"a.txt"}
    assert (tmp_path / "a.txt").read_bytes() == b"no nl"


def test_respects_nested_gitignore(tmp_path: pathlib.Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / ".gitignore").write_bytes(b"*.log\n")
    (sub / "x.log").write_bytes(b"no nl")
    (sub / "x.txt").write_bytes(b"no nl")
    fixed = _names(fix_directory(tmp_path))
    assert "sub/x.txt" in fixed
    assert "sub/x.log" not in fixed


def test_skips_binary(tmp_path: pathlib.Path) -> None:
    (tmp_path / "bin").write_bytes(b"a\x00b")
    assert fix_directory(tmp_path) == []
    assert (tmp_path / "bin").read_bytes() == b"a\x00b"


def test_default_excludes_cache_dirs(tmp_path: pathlib.Path) -> None:
    cache = tmp_path / ".cache"
    cache.mkdir()
    (cache / "blob").write_bytes(b"no nl")
    (tmp_path / "keep.txt").write_bytes(b"no nl")
    fixed = _names(fix_directory(tmp_path))
    assert "keep.txt" in fixed
    assert not any(name.startswith(".cache") for name in fixed)


def test_extra_excludes_augment_defaults(tmp_path: pathlib.Path) -> None:
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "lib.txt").write_bytes(b"no nl")
    (tmp_path / "keep.txt").write_bytes(b"no nl")
    fixed = _names(fix_directory(tmp_path, extra_excludes=["vendor"]))
    assert "keep.txt" in fixed
    assert not any(name.startswith("vendor") for name in fixed)


def test_symlink_does_not_crash(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "t.txt"
    target.write_bytes(b"no nl")
    link = tmp_path / "l.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):  # pragma: no cover
        pytest.skip("symlinks not available on this platform")
    fixed = _names(fix_directory(tmp_path))
    assert "t.txt" in fixed
    assert "l.txt" not in fixed


def test_runs_with_absolute_path_independent_of_cwd(tmp_path: pathlib.Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"no nl")
    assert _names(fix_directory(tmp_path.resolve())) == {"a.txt"}


def test_check_mode_opens_readonly_file_without_error(tmp_path: pathlib.Path) -> None:
    readonly = tmp_path / "ro.txt"
    readonly.write_bytes(b"no nl")
    readonly.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    try:
        fixed = _names(fix_directory(tmp_path, check=True))
        assert "ro.txt" in fixed
        assert readonly.read_bytes() == b"no nl"
    finally:
        readonly.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `just test tests/test_fixer.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'eof_fixer.fixer'`.

- [ ] **Step 3: Create `eof_fixer/fixer.py`**

```python
import os
import pathlib
from collections.abc import Iterator, Sequence
from typing import IO

from eof_fixer.discovery import iter_text_files

DEFAULT_EXCLUDES = (".cache", ".uv-cache")
_BINARY_SAMPLE_SIZE = 1024


def _is_binary(file_obj: IO[bytes]) -> bool:
    current_pos = file_obj.tell()
    file_obj.seek(0)
    sample = file_obj.read(_BINARY_SAMPLE_SIZE)
    file_obj.seek(current_pos)
    return b"\x00" in sample


def _detect_trailing(file_obj: IO[bytes]) -> tuple[str, int]:
    """Inspect the end of `file_obj` and return the action needed.

    Returns one of:
      - ("none", 0)           — file is empty, or already ends with exactly one terminator.
      - ("append_lf", 0)      — file lacks a trailing newline; an LF should be appended.
      - ("truncate", offset)  — file has excess trailing newlines; truncate to `offset`
                                (0 means truncate to empty).
    """
    try:
        file_obj.seek(-1, os.SEEK_END)
    except OSError:
        return ("none", 0)

    last_character = file_obj.read(1)
    if last_character not in {b"\n", b"\r"}:
        return ("append_lf", 0)

    while last_character in {b"\n", b"\r"}:
        if file_obj.tell() == 1:
            # All bytes are line terminators — truncate to empty.
            return ("truncate", 0)
        file_obj.seek(-2, os.SEEK_CUR)
        last_character = file_obj.read(1)

    position = file_obj.tell()
    remaining = file_obj.read()
    for sequence in (b"\n", b"\r\n", b"\r"):
        if remaining == sequence:
            return ("none", 0)
        if remaining.startswith(sequence):
            return ("truncate", position + len(sequence))

    return ("none", 0)  # pragma: no cover


def fix_file(file_obj: IO[bytes], *, check: bool) -> bool:
    """Normalize one open binary file to end with exactly one terminator.

    Returns True if the file was fixed (or, under `check`, would be fixed).
    Binary files (null byte in the first sample) are skipped, returning False.
    """
    if _is_binary(file_obj):
        return False

    action, offset = _detect_trailing(file_obj)
    if action == "none":
        return False

    if not check:
        if action == "append_lf":
            # Needs this seek for windows, otherwise IOError
            file_obj.seek(0, os.SEEK_END)
            file_obj.write(b"\n")
        else:  # action == "truncate"
            file_obj.seek(offset)
            file_obj.truncate()

    return True


def fix_directory(
    root: pathlib.Path,
    *,
    check: bool = False,
    extra_excludes: Sequence[str] = (),
) -> list[pathlib.Path]:
    """Fix every non-ignored text file under `root`; return the relative paths fixed.

    `.git` and `DEFAULT_EXCLUDES` (.cache/.uv-cache) are always skipped;
    `extra_excludes` adds more skip names on top. Under `check`, nothing is
    written but the would-be-fixed paths are still returned.
    """
    excludes = [*DEFAULT_EXCLUDES, *extra_excludes]
    open_mode = "rb" if check else "rb+"
    fixed: list[pathlib.Path] = []
    paths: Iterator[pathlib.Path] = iter_text_files(root, excludes)
    for relative_path in paths:
        with (root / relative_path).open(open_mode) as file_obj:
            if fix_file(file_obj, check=check):
                fixed.append(relative_path)
    return fixed
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `just test tests/test_fixer.py`
Expected: PASS — all content + orchestration tests green.

- [ ] **Step 5: Rewire `eof_fixer/main.py` to a thin adapter**

Replace the entire file with:

```python
import argparse
import pathlib
import sys

from eof_fixer.fixer import fix_directory


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="path to directory", type=pathlib.Path)
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        metavar="DIR",
        help="extra file/directory name to skip, in addition to .git, .cache, .uv-cache (repeatable)",
    )
    args = parser.parse_args()

    path: pathlib.Path = args.path
    if not path.is_dir():
        parser.error(f"path is not a directory: {path}")

    fixed = fix_directory(path, check=args.check, extra_excludes=args.exclude or [])
    for relative_path in fixed:
        sys.stdout.write(f"Fixing {relative_path}\n")
    return 1 if fixed else 0
```

(`_is_binary`, `_detect_trailing`, `_fix_file`, and the `os`/`IO` imports are gone — they live in `fixer.py` now.)

- [ ] **Step 6: Run the full suite**

Run: `just test`
Expected: PASS — `tests/test_fixer.py` plus the still-present `tests/test_end_of_file_fixer.py` (which drives `main()`); the `Fixing` lines are now batch-rendered but the substring/order assertions still hold. Coverage 100%.

- [ ] **Step 7: Lint**

Run: `just lint` (format as you go), then confirm a clean `just lint-ci` against the committed tree.

- [ ] **Step 8: Commit**

```bash
git add eof_fixer/fixer.py eof_fixer/main.py tests/test_fixer.py
git commit -m "refactor: deepen fix into fixer.py; main() becomes an adapter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Migrate `test_end_of_file_fixer.py` to adapter-only tests

**Files:**
- Modify: `tests/test_end_of_file_fixer.py`

**Interfaces:** Test-only. After Task 1, the behaviors in this file are now covered at the `fixer` layer by `tests/test_fixer.py`; this task removes the redundant process-harness tests, keeping only what genuinely exercises the `main()` adapter.

- [ ] **Step 1: Delete the now-redundant process-harness tests**

Remove these functions from `tests/test_end_of_file_fixer.py` (each is covered by `tests/test_fixer.py` as noted):
- `test_end_of_file_fixer_command_with_check_false` → `test_fixes_files_and_returns_list`
- `test_end_of_file_fixer_command_with_check_true` → `test_check_mode_writes_nothing`
- `test_end_of_file_fixer_with_gitignore` → `test_respects_nested_gitignore`
- `test_end_of_file_fixer_skips_binary_files` → `test_skips_binary`
- `test_crlf_no_trailing_newline_appends_lf` → `test_crlf_no_trailing_appends_lf`
- `test_crlf_perfect_unchanged` → `test_crlf_perfect_unchanged`
- `test_crlf_multiple_trailing_truncated_to_one` → `test_crlf_multiple_truncated_to_one`
- `test_cr_only_multiple_trailing_truncated_to_one` → `test_cr_only_multiple_truncated_to_one`
- `test_bom_prefixed_file_is_treated_as_text` → `test_bom_prefixed_is_treated_as_text`
- `test_null_byte_beyond_first_1024_bytes_is_treated_as_text` → `test_null_byte_beyond_first_1024_is_treated_as_text`
- `test_symlink_in_tree_does_not_crash` → `test_symlink_does_not_crash`
- `test_readonly_file_in_check_mode_does_not_raise` → `test_check_mode_opens_readonly_file_without_error`
- `test_exclude_flag_augments_default_skips` → `test_extra_excludes_augment_defaults`
- `test_runs_from_unrelated_cwd_with_absolute_path` → `test_runs_with_absolute_path_independent_of_cwd`

Keep `test_path_arg_rejects_file` and `test_path_arg_rejects_nonexistent_path` (they exercise the argparse `is_dir` guard → exit 2, which only `main()` does).

- [ ] **Step 2: Add two adapter tests that exercise `main()`'s rendering**

Keep the existing `_run_main_in` helper (the kept + new tests use it). Add:

```python
def test_main_renders_fixing_lines_and_exit_code() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "a.txt").write_bytes(b"no nl")
        skipped = temp_path / "vendor"
        skipped.mkdir()
        (skipped / "lib.txt").write_bytes(b"no nl")

        with _run_main_in(temp_path, ["eof-fixer", ".", "--exclude", "vendor"]) as (stdout, _stderr):
            result = main()

        output = stdout.getvalue()
        assert result == 1
        assert "Fixing a.txt\n" in output
        assert "Fixing vendor/lib.txt\n" not in output


def test_main_returns_zero_when_nothing_to_fix() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "ok.txt").write_bytes(b"already fine\n")

        with _run_main_in(temp_path, ["eof-fixer", "."]) as (stdout, _stderr):
            result = main()

        assert result == 0
        assert stdout.getvalue() == ""
```

- [ ] **Step 3: Prune now-unused imports**

After deletion, remove any imports left unused in `tests/test_end_of_file_fixer.py` (e.g. `shutil`, `stat`, `StringIO` if no longer referenced). Let `just lint` (ruff `F401`) tell you which; remove exactly those.

- [ ] **Step 4: Run the full suite + coverage**

Run: `just test`
Expected: PASS, coverage 100%. The adapter tests cover `main()`'s render loop, exit-0 path, `--exclude` wiring, and both `is_dir` rejections; `fixer.py` is covered by `tests/test_fixer.py`. If coverage flags an uncovered line in `main.py`, add the minimal adapter test that reaches it (do not add `# pragma: no cover` to adapter logic).

- [ ] **Step 5: Lint**

Run: `just lint`, then confirm `just lint-ci` clean against the committed tree.

- [ ] **Step 6: Commit**

```bash
git add tests/test_end_of_file_fixer.py
git commit -m "test: move fix behavior off the process harness to the fixer interface

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Promote to architecture + finalize the bundle summary

**Files:**
- Modify: `architecture/eof-normalization.md`
- Modify: `architecture/cli.md`
- Modify: `planning/changes/2026-06-26.02-deepen-fixer/design.md` (finalize `summary`)

**Interfaces:** Documentation only.

- [ ] **Step 1: Update `architecture/eof-normalization.md`**

Read the file first. Update it so the capability is described as living in `eof_fixer/fixer.py`: the public `fix_file(file_obj, *, check) -> bool` (one open file) and `fix_directory(root, *, check, extra_excludes) -> list[Path]` (drives `discovery.iter_text_files`, owns the `DEFAULT_EXCLUDES` = `.cache`/`.uv-cache` policy, opens `rb`/`rb+` by `check`, returns the fixed relative paths). Note `main()` no longer holds the file-level logic. Preserve the existing action-model / terminator prose.

- [ ] **Step 2: Update `architecture/cli.md`**

Read the file first. Update it so `main()` is described as a thin adapter over `fix_directory`: it parses args, guards `is_dir` (exit 2), then renders one `Fixing <path>` line per returned path and exits `1`/`0`. Note the output is now batch-rendered after the walk (not streamed). The `--exclude` and exit-code contract are unchanged.

- [ ] **Step 3: Finalize the bundle summary**

In `planning/changes/2026-06-26.02-deepen-fixer/design.md`, change the frontmatter `summary:` to the realized result, e.g.:
`summary: Fix behavior now lives behind eof_fixer/fixer.py (fix_file + fix_directory); main() is a thin adapter and tests target the interface instead of the argv/stdout/cwd harness.`

- [ ] **Step 4: Validate + lint**

Run: `just check-planning` → expect `planning: OK`.
Run: `just lint-ci` → expect clean.

- [ ] **Step 5: Commit**

```bash
git add architecture/eof-normalization.md architecture/cli.md \
  planning/changes/2026-06-26.02-deepen-fixer/design.md
git commit -m "docs: promote the fixer deepening to architecture

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria

- `eof_fixer/fixer.py` exposes `fix_file` + `fix_directory`; `main.py` is a thin adapter with no file-level logic.
- Behavior unchanged except streaming → batch output; existing exit codes, `Fixing` lines, gitignore/`--exclude`/binary/symlink behavior preserved.
- Tests target the `fixer` interface (content via `BytesIO`, orchestration via `fix_directory`); only path-rejection + two render tests go through `main()`. `_run_main_in` serves just those.
- `just test` green, coverage 100%; `just lint-ci` clean; `just check-planning` → `planning: OK`.
- `architecture/eof-normalization.md` + `architecture/cli.md` describe the new structure; bundle summary finalized.
