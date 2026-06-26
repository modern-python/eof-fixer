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


def test_empty_real_file_unchanged(tmp_path: pathlib.Path) -> None:
    # BytesIO(b"") handles seek(-1, SEEK_END) without error; a real empty file
    # raises OSError, exercising the except branch in _detect_trailing.
    empty = tmp_path / "empty.txt"
    empty.write_bytes(b"")
    with empty.open("rb+") as f:
        assert fix_file(f, check=False) is False
    assert empty.read_bytes() == b""


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
