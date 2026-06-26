import os
import shutil
import stat
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


def test_end_of_file_fixer_command_with_check_false() -> None:
    # Create a temporary directory with test files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy fixture files to temp directory
        fixtures_dir = Path(__file__).parent / "fixtures"
        for fixture_file in fixtures_dir.glob("*.txt"):
            shutil.copy(fixture_file, temp_path / fixture_file.name)

        # Change to the temp directory and capture stdout
        original_cwd = Path.cwd()
        original_argv = sys.argv
        original_stdout = sys.stdout
        captured_output = StringIO()

        try:
            os.chdir(temp_dir)
            sys.argv = ["eof-fixer", "."]
            sys.stdout = captured_output

            # Run eof-fixer . command
            result = main()

            # Should exit with code 1 (since some files needed fixing)
            assert result == 1

            # Should output which files are being fixed
            output = captured_output.getvalue()
            assert "Fixing no_newline.txt\n" in output
            assert "Fixing multiple_newlines.txt\n" in output
            assert "Fixing newlines_only.txt\n" in output

        finally:
            os.chdir(original_cwd)
            sys.argv = original_argv
            sys.stdout = original_stdout

        # Check that files were fixed correctly
        # File with no newline should now have one
        no_newline_content = (temp_path / "no_newline.txt").read_text()
        assert no_newline_content == "This file has no newline at the end\n"

        # File with one newline should be unchanged
        one_newline_content = (temp_path / "one_newline.txt").read_text()
        assert one_newline_content == "This file has exactly one newline at the end\n"

        # File with multiple newlines should be truncated to one
        multiple_newlines_content = (temp_path / "multiple_newlines.txt").read_text()
        assert multiple_newlines_content == "This file has multiple newlines at the end\n"

        # File with only newlines should be made empty
        newlines_only_content = (temp_path / "newlines_only.txt").read_text()
        assert newlines_only_content == ""

        # Perfect file should be unchanged
        perfect_content = (temp_path / "perfect.txt").read_text()
        assert perfect_content == "This file already has exactly one newline at the end\n"

        # Empty file should remain empty
        empty_content = (temp_path / "empty.txt").read_text()
        assert empty_content == ""


def test_end_of_file_fixer_command_with_check_true() -> None:
    # Create a temporary directory with test files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy fixture files to temp directory
        fixtures_dir = Path(__file__).parent / "fixtures"
        for fixture_file in fixtures_dir.glob("*.txt"):
            shutil.copy(fixture_file, temp_path / fixture_file.name)

        # Change to the temp directory and capture stdout
        original_cwd = Path.cwd()
        original_argv = sys.argv
        original_stdout = sys.stdout
        captured_output = StringIO()

        try:
            os.chdir(temp_dir)
            sys.argv = ["eof-fixer", ".", "--check"]
            sys.stdout = captured_output

            # Run eof-fixer . --check command
            result = main()

            # Should exit with code 1 (since some files need fixing)
            assert result == 1

            # Should output which files need fixing
            output = captured_output.getvalue()
            assert "Fixing no_newline.txt\n" in output
            assert "Fixing multiple_newlines.txt\n" in output
            assert "Fixing newlines_only.txt\n" in output

        finally:
            os.chdir(original_cwd)
            sys.argv = original_argv
            sys.stdout = original_stdout

        # Files should be unchanged in check mode
        no_newline_content = (temp_path / "no_newline.txt").read_text()
        assert no_newline_content == "This file has no newline at the end"  # Unchanged

        one_newline_content = (temp_path / "one_newline.txt").read_text()
        assert one_newline_content == "This file has exactly one newline at the end\n"  # Unchanged

        multiple_newlines_content = (temp_path / "multiple_newlines.txt").read_text()
        assert multiple_newlines_content == "This file has multiple newlines at the end\n\n"  # Unchanged

        newlines_only_content = (temp_path / "newlines_only.txt").read_text()
        assert newlines_only_content == "\n\n\n"  # Unchanged

        perfect_content = (temp_path / "perfect.txt").read_text()
        assert perfect_content == "This file already has exactly one newline at the end\n"  # Unchanged

        empty_content = (temp_path / "empty.txt").read_text()
        assert empty_content == ""  # Unchanged


def test_end_of_file_fixer_with_gitignore() -> None:
    # Create a temporary directory with test files including .gitignore
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy all fixture files to temp directory
        fixtures_dir = Path(__file__).parent / "fixtures"
        for fixture_file in fixtures_dir.glob("*"):
            assert shutil.copy(fixture_file, temp_path / fixture_file.name)

        Path(temp_path / ".gitignore").write_text("*.tmp")

        # Change to the temp directory and capture stdout
        original_cwd = Path.cwd()
        original_argv = sys.argv
        original_stdout = sys.stdout
        captured_output = StringIO()

        try:
            os.chdir(temp_dir)
            sys.argv = ["eof-fixer", "."]
            sys.stdout = captured_output

            # Run eof-fixer . command
            result = main()

            # Should exit with code 1 (since some files needed fixing)
            assert result == 1

            # Should output which files are being fixed
            output = captured_output.getvalue()
            assert "Fixing no_newline.txt\n" in output
            assert "Fixing multiple_newlines.txt\n" in output
            assert "Fixing newlines_only.txt\n" in output
            # Should NOT mention the .tmp file since it's ignored by .gitignore
            assert "Fixing temp_file.tmp\n" not in output

        finally:
            os.chdir(original_cwd)
            sys.argv = original_argv
            sys.stdout = original_stdout

        # Check that files were fixed correctly
        # File with no newline should now have one
        no_newline_content = (temp_path / "no_newline.txt").read_text()
        assert no_newline_content == "This file has no newline at the end\n"

        # File with multiple newlines should be truncated to one
        multiple_newlines_content = (temp_path / "multiple_newlines.txt").read_text()
        assert multiple_newlines_content == "This file has multiple newlines at the end\n"

        # File with only newlines should be made empty
        newlines_only_content = (temp_path / "newlines_only.txt").read_text()
        assert newlines_only_content == ""

        # The .tmp file should be unchanged since it's ignored
        temp_file_content = (temp_path / "temp_file.tmp").read_text()
        assert temp_file_content == "This is a temporary file that should be ignored"


def test_end_of_file_fixer_skips_binary_files() -> None:
    # Create a temporary directory with test files including a binary file
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Copy all fixture files to temp directory
        fixtures_dir = Path(__file__).parent / "fixtures"
        for fixture_file in fixtures_dir.glob("*"):
            assert shutil.copy(fixture_file, temp_path / fixture_file.name)

        # Create a binary file with null bytes
        binary_file = temp_path / "binary_file.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\x04\x05")

        # Also create a text file without newline that should be fixed
        text_file = temp_path / "text_no_newline.txt"
        text_file.write_text("This is a text file without newline")

        # Change to the temp directory and capture stdout
        original_cwd = Path.cwd()
        original_argv = sys.argv
        original_stdout = sys.stdout
        captured_output = StringIO()

        try:
            os.chdir(temp_dir)
            sys.argv = ["eof-fixer", "."]
            sys.stdout = captured_output

            # Run eof-fixer . command
            result = main()

            # Should exit with code 1 (since the text file needed fixing)
            assert result == 1

            # Should output that the text file is being fixed
            output = captured_output.getvalue()
            assert "Fixing text_no_newline.txt\n" in output
            # Should NOT mention the binary file
            assert "Fixing binary_file.bin\n" not in output

        finally:
            os.chdir(original_cwd)
            sys.argv = original_argv
            sys.stdout = original_stdout

        # Check that text file was fixed
        text_content = (temp_path / "text_no_newline.txt").read_text()
        assert text_content == "This is a text file without newline\n"

        # Check that binary file was not modified
        binary_content = (temp_path / "binary_file.bin").read_bytes()
        assert binary_content == b"\x00\x01\x02\x03\x04\x05"


def test_crlf_no_trailing_newline_appends_lf() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target = temp_path / "crlf_no_newline.txt"
        target.write_bytes(b"a\r\nb")

        with _run_main_in(temp_path, ["eof-fixer", "."]) as (stdout, _stderr):
            result = main()

        assert result == 1
        assert "Fixing crlf_no_newline.txt\n" in stdout.getvalue()
        # LF is appended even though the file uses CRLF — documented behavior.
        assert target.read_bytes() == b"a\r\nb\n"


def test_crlf_perfect_unchanged() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target = temp_path / "crlf_perfect.txt"
        target.write_bytes(b"a\r\n")

        with _run_main_in(temp_path, ["eof-fixer", "."]) as (stdout, _stderr):
            result = main()

        assert result == 0
        assert stdout.getvalue() == ""
        assert target.read_bytes() == b"a\r\n"


def test_crlf_multiple_trailing_truncated_to_one() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target = temp_path / "crlf_multiple.txt"
        target.write_bytes(b"a\r\n\r\n\r\n")

        with _run_main_in(temp_path, ["eof-fixer", "."]) as (stdout, _stderr):
            result = main()

        assert result == 1
        assert "Fixing crlf_multiple.txt\n" in stdout.getvalue()
        assert target.read_bytes() == b"a\r\n"


def test_cr_only_multiple_trailing_truncated_to_one() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target = temp_path / "cr_only.txt"
        target.write_bytes(b"a\r\r\r")

        with _run_main_in(temp_path, ["eof-fixer", "."]) as (stdout, _stderr):
            result = main()

        assert result == 1
        assert "Fixing cr_only.txt\n" in stdout.getvalue()
        assert target.read_bytes() == b"a\r"


def test_bom_prefixed_file_is_treated_as_text() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target = temp_path / "bom_no_newline.txt"
        target.write_bytes(b"\xef\xbb\xbfhello")

        with _run_main_in(temp_path, ["eof-fixer", "."]) as (stdout, _stderr):
            result = main()

        assert result == 1
        assert "Fixing bom_no_newline.txt\n" in stdout.getvalue()
        assert target.read_bytes() == b"\xef\xbb\xbfhello\n"


def test_null_byte_beyond_first_1024_bytes_is_treated_as_text() -> None:
    # _is_binary inspects only the first 1024 bytes, so a null byte past that
    # boundary does NOT mark the file as binary. Document the current behavior.
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target = temp_path / "late_null.txt"
        payload = b"a" * 2000 + b"\x00" + b"b"
        target.write_bytes(payload)

        with _run_main_in(temp_path, ["eof-fixer", "."]) as (stdout, _stderr):
            result = main()

        assert result == 1
        assert "Fixing late_null.txt\n" in stdout.getvalue()
        assert target.read_bytes() == payload + b"\n"


def test_symlink_in_tree_does_not_crash() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        target = temp_path / "target.txt"
        target.write_bytes(b"contents without newline")
        link = temp_path / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):  # pragma: no cover
            pytest.skip("symlinks not available on this platform")

        with _run_main_in(temp_path, ["eof-fixer", "."]) as (_stdout, _stderr):
            result = main()

        # Either path (link followed or skipped) is acceptable — but the
        # walked target itself must end up fixed and the tool must not crash.
        assert result == 1
        assert target.read_bytes().endswith(b"\n")


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


def test_readonly_file_in_check_mode_does_not_raise() -> None:
    # In --check mode no writes occur, so the file should be opened read-only
    # and not raise on read-only files.
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        readonly = temp_path / "readonly.txt"
        readonly.write_text("no newline")
        readonly.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        try:
            with _run_main_in(temp_path, ["eof-fixer", ".", "--check"]) as (stdout, _stderr):
                result = main()

            assert result == 1
            assert "Fixing readonly.txt\n" in stdout.getvalue()
            # File must still be unchanged in check mode.
            assert readonly.read_text() == "no newline"
        finally:
            # Restore writable bits so the tempdir can be cleaned up.
            readonly.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


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


def test_runs_from_unrelated_cwd_with_absolute_path() -> None:
    # Regression test: the tool should work when invoked with an absolute path
    # that is not the caller's cwd. Previously yielded relative names were
    # opened against cwd, causing FileNotFoundError.
    with tempfile.TemporaryDirectory() as work_dir, tempfile.TemporaryDirectory() as target_dir:
        work_path = Path(work_dir)
        target_path = Path(target_dir)
        target_file = target_path / "needs_fix.txt"
        target_file.write_text("no newline")

        with _run_main_in(work_path, ["eof-fixer", str(target_path)]) as (stdout, _stderr):
            result = main()

        assert result == 1
        assert "Fixing needs_fix.txt\n" in stdout.getvalue()
        assert target_file.read_text() == "no newline\n"
