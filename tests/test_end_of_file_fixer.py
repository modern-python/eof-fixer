import os
import shutil
import sys
import tempfile
from io import StringIO
from pathlib import Path

from eof_fixer.main import main


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
            assert "no_newline.txt" in output
            assert "multiple_newlines.txt" in output
            assert "newlines_only.txt" in output

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
            assert "no_newline.txt" in output
            assert "multiple_newlines.txt" in output
            assert "newlines_only.txt" in output

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
            assert "no_newline.txt" in output
            assert "multiple_newlines.txt" in output
            assert "newlines_only.txt" in output
            # Should NOT mention the .tmp file since it's ignored by .gitignore
            assert "temp_file.tmp" not in output

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
            assert "text_no_newline.txt" in output
            # Should NOT mention the binary file
            assert "binary_file.bin" not in output

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
