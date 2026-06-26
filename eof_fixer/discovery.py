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
        # rel is always within anchor's subtree: specs are popped on leaving their dir.
        # (anchor "" → removeprefix("/") leaves rel unchanged, since rel has no leading slash.)
        subpath = rel.removeprefix(anchor + "/")
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
    baseline = GitIgnoreSpec.from_lines(extra_excludes)
    stack: list[tuple[str, GitIgnoreSpec]] = [("", baseline)]
    yield from _walk(root, "", stack)
