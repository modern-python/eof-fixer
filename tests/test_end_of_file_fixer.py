import os
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import pytest

from eof_fixer.main import main


@contextmanager
def _run_main_in(temp_dir: Path, argv: list[str]) -> Iterator[tuple[StringIO, StringIO]]:
    """Swap cwd, argv, stdout, stderr around a ``main()`` call."""
    captured_stdout = StringIO()
    captured_stderr = StringIO()
    original_cwd = Path.cwd()
    original_argv = sys.argv
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    try:
        os.chdir(temp_dir)
        sys.argv = argv
        sys.stdout = captured_stdout
        sys.stderr = captured_stderr
        yield captured_stdout, captured_stderr
    finally:
        os.chdir(original_cwd)
        sys.argv = original_argv
        sys.stdout = original_stdout
        sys.stderr = original_stderr


def test_path_arg_rejects_file() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        not_a_dir = temp_path / "regular.txt"
        not_a_dir.write_text("hi\n")

        with (
            _run_main_in(temp_path, ["eof-fixer", str(not_a_dir)]) as (_stdout, stderr),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code != 0
        assert "is not a directory" in stderr.getvalue()
        assert str(not_a_dir) in stderr.getvalue()


def test_path_arg_rejects_nonexistent_path() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        missing = temp_path / "does-not-exist"

        with (
            _run_main_in(temp_path, ["eof-fixer", str(missing)]) as (_stdout, stderr),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code != 0
        assert "is not a directory" in stderr.getvalue()


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
