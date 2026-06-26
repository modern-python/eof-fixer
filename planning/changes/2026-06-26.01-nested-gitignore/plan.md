# Nested `.gitignore` Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the file walk honor nested per-directory `.gitignore` files (not just the root) and expose the extra skip dirs through a repeatable `--exclude` flag.

**Architecture:** A new `eof_fixer/discovery.py` module owns "which files to visit": a top-down DFS that carries a stack of `(anchor_dir, GitIgnoreSpec)`, evaluates each entry deepest-spec-first (first definitive `check_file(...).include` wins), prunes ignored directories, hard-skips `.git`, and skips symlinks. `main()` keeps the unchanged EOF core (`_is_binary`, `_detect_trailing`, `_fix_file`) and just consumes the new iterator.

**Tech Stack:** Python 3.10+, `pathspec.GitIgnoreSpec` (existing dependency — no new deps), pytest.

## Global Constraints

- Python `>=3.10,<4`; code must run on 3.10–3.14 (no 3.11+-only syntax).
- Runtime dependencies: **`pathspec` only** — add no new dependency.
- All imports at module level, never inside function bodies.
- Type-checker suppressions use `ty: ignore`, never `# type: ignore`.
- No `print()` in source — emit via `sys.stdout.write(...)` with an explicit `\n` (see `planning/decisions/2026-06-26-no-print-in-source.md`).
- Annotate test function arguments (e.g. `tmp_path: pathlib.Path`).
- ruff line length 120; `just lint` must be clean.
- Conventional-commit messages, each ending with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- This is a Full-lane planning change: the implementing PR hand-edits the matching `architecture/*.md` files (Task 3).

---

### Task 1: `discovery.py` — the nested-gitignore walk

**Files:**
- Create: `eof_fixer/discovery.py`
- Test: `tests/test_discovery.py`

**Interfaces:**
- Consumes: `pathspec.GitIgnoreSpec` (`.from_lines`, `.check_file(path).include` → `True`/`False`/`None`). For directory entries, the path passed to `check_file` MUST carry a trailing `/`.
- Produces: `iter_text_files(root: pathlib.Path, extra_excludes: Sequence[str]) -> Iterator[pathlib.Path]`, yielding paths **relative to `root`** (posix `/` separators) for files not ignored.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_discovery.py
import pathlib

import pytest

from eof_fixer.discovery import iter_text_files


def _walk(root: pathlib.Path, extra_excludes: list[str] | None = None) -> set[str]:
    return {str(p) for p in iter_text_files(root, extra_excludes or [])}


def test_root_gitignore_excludes_matching_files(tmp_path: pathlib.Path) -> None:
    (tmp_path / "keep.txt").write_text("x")
    (tmp_path / "skip.tmp").write_text("x")
    (tmp_path / ".gitignore").write_text("*.tmp\n")
    result = _walk(tmp_path)
    assert "keep.txt" in result
    assert "skip.tmp" not in result
    assert ".gitignore" in result


def test_extra_excludes_are_skipped(tmp_path: pathlib.Path) -> None:
    (tmp_path / "keep.txt").write_text("x")
    cache = tmp_path / ".cache"
    cache.mkdir()
    (cache / "blob").write_text("x")
    result = _walk(tmp_path, [".cache", ".uv-cache"])
    assert "keep.txt" in result
    assert not any(name.startswith(".cache") for name in result)


def test_nested_gitignore_applies_to_its_subtree(tmp_path: pathlib.Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / ".gitignore").write_text("*.log\n")
    (sub / "a.log").write_text("x")
    (sub / "a.txt").write_text("x")
    (tmp_path / "top.log").write_text("x")  # not under sub → not ignored
    result = _walk(tmp_path)
    assert "sub/a.txt" in result
    assert "sub/a.log" not in result
    assert "top.log" in result


def test_deeper_gitignore_overrides_shallower(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".gitignore").write_text("*.log\n")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / ".gitignore").write_text("!important.log\n")
    (sub / "important.log").write_text("x")
    (sub / "other.log").write_text("x")
    result = _walk(tmp_path)
    assert "sub/important.log" in result
    assert "sub/other.log" not in result


def test_negation_reincludes_file(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".gitignore").write_text("*.log\n!keep.log\n")
    (tmp_path / "a.log").write_text("x")
    (tmp_path / "keep.log").write_text("x")
    result = _walk(tmp_path)
    assert "a.log" not in result
    assert "keep.log" in result


def test_ignored_directory_is_pruned(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".gitignore").write_text("build/\n")
    build = tmp_path / "build"
    build.mkdir()
    (build / "out.txt").write_text("x")
    (build / ".gitignore").write_text("!out.txt\n")  # cannot re-include under ignored dir
    result = _walk(tmp_path)
    assert not any(name.startswith("build") for name in result)


def test_git_directory_is_always_skipped(tmp_path: pathlib.Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("x")
    (tmp_path / "keep.txt").write_text("x")
    result = _walk(tmp_path)
    assert "keep.txt" in result
    assert not any(name.startswith(".git/") for name in result)


def test_symlinks_are_skipped(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("x")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):  # pragma: no cover
        pytest.skip("symlinks not available on this platform")
    result = _walk(tmp_path)
    assert "target.txt" in result
    assert "link.txt" not in result
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `just test tests/test_discovery.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'eof_fixer.discovery'`.

- [ ] **Step 3: Implement `eof_fixer/discovery.py`**

```python
import os
import pathlib
from collections.abc import Iterator, Sequence

from pathspec import GitIgnoreSpec

GITIGNORE_NAME = ".gitignore"
ALWAYS_PRUNE = ".git"


def _load_spec(directory: pathlib.Path) -> GitIgnoreSpec | None:
    """Parse a directory's .gitignore into a spec, or None if it has none."""
    gitignore = directory / GITIGNORE_NAME
    if not gitignore.is_file():
        return None
    return GitIgnoreSpec.from_lines(gitignore.read_text(encoding="utf-8").splitlines())


def _is_ignored(rel: str, is_dir: bool, stack: list[tuple[str, GitIgnoreSpec]]) -> bool:
    """Evaluate specs deepest-first; first definitive verdict wins (git precedence)."""
    suffix = "/" if is_dir else ""
    for anchor, spec in reversed(stack):
        subpath = rel if not anchor else rel[len(anchor) + 1 :]
        result = spec.check_file(subpath + suffix)
        if result.include is not None:
            return result.include
    return False


def _walk(
    directory: pathlib.Path,
    rel_dir: str,
    stack: list[tuple[str, GitIgnoreSpec]],
) -> Iterator[pathlib.Path]:
    """Depth-first walk, pushing each directory's .gitignore onto the spec stack."""
    spec = _load_spec(directory)
    if spec is not None:
        stack.append((rel_dir, spec))
    try:
        with os.scandir(directory) as scan:
            entries = sorted(scan, key=lambda entry: entry.name)
        for entry in entries:
            if entry.name == ALWAYS_PRUNE or entry.is_symlink():
                continue
            is_dir = entry.is_dir()
            rel = entry.name if not rel_dir else f"{rel_dir}/{entry.name}"
            if _is_ignored(rel, is_dir, stack):
                continue
            if is_dir:
                yield from _walk(pathlib.Path(entry.path), rel, stack)
            else:
                yield pathlib.Path(rel)
    finally:
        if spec is not None:
            stack.pop()


def iter_text_files(root: pathlib.Path, extra_excludes: Sequence[str]) -> Iterator[pathlib.Path]:
    """Yield paths (relative to root) of files not ignored by nested .gitignore files.

    `.git` is always skipped. `extra_excludes` (e.g. ['.cache', '.uv-cache']) form a
    baseline gitignore spec anchored at root, applied beneath every .gitignore file.
    """
    baseline = GitIgnoreSpec.from_lines(list(extra_excludes))
    stack: list[tuple[str, GitIgnoreSpec]] = [("", baseline)]
    yield from _walk(root, "", stack)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `just test tests/test_discovery.py`
Expected: PASS — all 8 tests green.

- [ ] **Step 5: Lint**

Run: `just lint`
Expected: ruff format/check and ty all clean.

- [ ] **Step 6: Commit**

```bash
git add eof_fixer/discovery.py tests/test_discovery.py
git commit -m "feat: add nested .gitignore-aware file discovery

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Wire discovery into `main()` and add `--exclude`

**Files:**
- Modify: `eof_fixer/main.py` (replace the gitignore-loading block and the walk in `main()`; drop the `pathspec` import)
- Test: `tests/test_end_of_file_fixer.py` (existing suite must stay green; add one `--exclude` test)

**Interfaces:**
- Consumes: `iter_text_files(root, extra_excludes)` from Task 1.
- Produces: no new public symbols. CLI gains `--exclude DIR` (repeatable, `action="append"`). Extra-exclude set is `[".cache", ".uv-cache", *args.exclude]`; `.git` is skipped by discovery and is not configurable.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_end_of_file_fixer.py` (it already imports `main`, `Path`, `os`, `sys`, `StringIO`, `tempfile`, `shutil`; reuse the existing `_run_main_in` helper used by other tests):

```python
def test_exclude_flag_augments_default_skips() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        (temp_path / "keep.txt").write_bytes(b"no newline")
        vendor = temp_path / "vendor"
        vendor.mkdir()
        (vendor / "lib.txt").write_bytes(b"no newline")

        with _run_main_in(temp_path, ["eof-fixer", ".", "--exclude", "vendor"]) as (stdout, _stderr):
            result = main()

        output = stdout.getvalue()
        assert result == 1
        assert "Fixing keep.txt\n" in output
        assert "Fixing vendor/lib.txt\n" not in output
        # vendor file left untouched because it was excluded
        assert (vendor / "lib.txt").read_bytes() == b"no newline"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `just test tests/test_end_of_file_fixer.py::test_exclude_flag_augments_default_skips`
Expected: FAIL — `--exclude` is an unrecognized argument (argparse SystemExit), so `main()` never runs the assertions.

- [ ] **Step 3: Edit `main()`**

In `eof_fixer/main.py`, remove `import pathspec` (keep `import os`, used by the EOF core). Add the discovery import at module level:

```python
from eof_fixer.discovery import iter_text_files
```

Replace the body of `main()` from the argument parser through the end with:

```python
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
    check: bool = args.check

    if not path.is_dir():
        parser.error(f"path is not a directory: {path}")

    extra_excludes = [".cache", ".uv-cache", *(args.exclude or [])]
    open_mode = "rb" if check else "rb+"

    retv = 0
    for relative_path in iter_text_files(path, extra_excludes):
        with (path / relative_path).open(open_mode) as f:
            ret_for_file = _fix_file(f, check=check)
            if ret_for_file:
                sys.stdout.write(f"Fixing {relative_path}\n")
            retv |= ret_for_file

    return retv
```

(The hardcoded `ignore_patterns` list, the `.gitignore` file read, the `GitIgnoreSpec` construction, and the `match_tree_files` loop are all deleted — discovery now owns them.)

- [ ] **Step 4: Run the new test and the full suite**

Run: `just test`
Expected: PASS — the new `--exclude` test and every existing test (including `test_end_of_file_fixer_with_gitignore`, `test_symlink_in_tree_does_not_crash`, the CRLF/CR cases, and the path/readonly/cwd tests) are green. Coverage stays at the configured threshold.

- [ ] **Step 5: Lint**

Run: `just lint`
Expected: clean. Confirm `import pathspec` is gone from `main.py` (it now lives only in `discovery.py`).

- [ ] **Step 6: Commit**

```bash
git add eof_fixer/main.py tests/test_end_of_file_fixer.py
git commit -m "feat: respect nested .gitignore and add --exclude flag

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Promote to architecture + record the decision

**Files:**
- Modify: `architecture/file-discovery.md`
- Modify: `architecture/cli.md`
- Create: `planning/decisions/2026-06-26-build-on-pathspec-for-nested-gitignore.md`
- Modify: `planning/changes/2026-06-26.01-nested-gitignore/design.md` (finalize `summary`)

**Interfaces:** Documentation only — no code, no new symbols.

- [ ] **Step 1: Update `architecture/file-discovery.md`**

Replace the "Ignore rules" and "Path resolution" sections so they describe the nested walk. The new prose must state:
- Discovery lives in `eof_fixer/discovery.py` (`iter_text_files`); `main()` consumes it.
- The walk is a top-down DFS carrying a stack of per-directory `GitIgnoreSpec`s; an entry is classified by evaluating specs deepest-first, first definitive `check_file().include` wins (git precedence: closest file wins, negation re-includes).
- `.git` is always pruned by name; symlinks are skipped; ignored directories are pruned (git-correct — a file under an excluded parent cannot be re-included).
- The baseline excludes (`.cache`, `.uv-cache`, plus any `--exclude` values) form a root-anchored spec beneath every `.gitignore`.
- Still pure-filesystem: no `.git/info/exclude`, no global `core.excludesFile`, no git invocation; works on any directory.

- [ ] **Step 2: Update `architecture/cli.md`**

Under the interface description, document `--exclude DIR` (repeatable): adds extra file/directory names to skip on top of the always-skipped `.git` and the default `.cache`/`.uv-cache`. Note `.git` is not configurable.

- [ ] **Step 3: Create the decision record**

```markdown
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
```

- [ ] **Step 4: Finalize the bundle summary**

In `planning/changes/2026-06-26.01-nested-gitignore/design.md`, update the frontmatter `summary:` from the intent line to the realized result, e.g.:
`summary: Nested .gitignore files are now respected tree-wide (DFS over per-directory pathspec specs) and a repeatable --exclude flag augments the default skip dirs.`

- [ ] **Step 5: Validate planning + lint**

Run: `just check-planning`
Expected: `planning: OK` (decision name/frontmatter valid, bundle shape valid).
Run: `just lint-ci`
Expected: clean, including `check-planning`.

- [ ] **Step 6: Commit**

```bash
git add architecture/file-discovery.md architecture/cli.md \
  planning/decisions/2026-06-26-build-on-pathspec-for-nested-gitignore.md \
  planning/changes/2026-06-26.01-nested-gitignore/design.md
git commit -m "docs: promote nested .gitignore to architecture + record decision

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Done criteria

- `just test` green on 3.10–3.14; `tests/test_discovery.py` covers nested precedence, negation, directory pruning, `.git` skip, symlink skip, and extra-excludes.
- `eof-fixer` honors `.gitignore` files in subdirectories; `--exclude` augments the default skip set; `.git`/`.cache`/`.uv-cache` still skipped by default.
- No new runtime dependency (pathspec only).
- `architecture/file-discovery.md` + `architecture/cli.md` describe the new behavior; decision recorded; `just check-planning` → `planning: OK`.
