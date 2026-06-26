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
