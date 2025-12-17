import argparse
import os
import pathlib
import sys
from typing import IO

import pathspec


def _is_binary(file_obj: IO[bytes]) -> bool:
    current_pos = file_obj.tell()
    file_obj.seek(0)
    sample = file_obj.read(1024)
    file_obj.seek(current_pos)
    return b"\x00" in sample


def _fix_file(file_obj: IO[bytes], check: bool) -> int:  # noqa: C901, PLR0911
    # Skip binary files
    if _is_binary(file_obj):
        return 0

    # Test for newline at end of file
    # Empty files will throw IOError here
    try:
        file_obj.seek(-1, os.SEEK_END)
    except OSError:
        return 0

    last_character = file_obj.read(1)
    # last_character will be '' for an empty file
    if last_character not in {b"\n", b"\r"} and last_character != b"":
        if not check:
            # Needs this seek for windows, otherwise IOError
            file_obj.seek(0, os.SEEK_END)
            file_obj.write(b"\n")
        return 1

    while last_character in {b"\n", b"\r"}:
        # Deal with the beginning of the file
        if file_obj.tell() == 1:
            if not check:
                # If we've reached the beginning of the file and it is all
                # linebreaks then we can make this file empty
                file_obj.seek(0)
                file_obj.truncate()
            return 1

        # Go back two bytes and read a character
        file_obj.seek(-2, os.SEEK_CUR)
        last_character = file_obj.read(1)

    # Our current position is at the end of the file just before any amount of
    # newlines.  If we find extraneous newlines, then backtrack and trim them.
    position = file_obj.tell()
    remaining = file_obj.read()
    for sequence in (b"\n", b"\r\n", b"\r"):
        if remaining == sequence:
            return 0

        if remaining.startswith(sequence):
            if not check:
                file_obj.seek(position + len(sequence))
                file_obj.truncate()
            return 1

    return 0  # pragma: no cover


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="path to directory", type=pathlib.Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    path: pathlib.Path = args.path
    check: bool = args.check
    gitignore_path = path / ".gitignore"

    ignore_patterns = [
        ".git",
        ".cache",  # for uv cache
        ".uv-cache",  # for uv cache
    ]
    if gitignore_path.exists():
        with gitignore_path.open("r") as f:
            ignore_patterns.extend(f.readlines())

    gitignore_spec = pathspec.GitIgnoreSpec.from_lines(ignore_patterns)

    retv = 0
    for filename in gitignore_spec.match_tree(path, negate=True):
        with pathlib.Path(filename).open("rb+") as f:
            ret_for_file = _fix_file(f, check=check)
            if ret_for_file:
                sys.stdout.write(f"Fixing {filename}")
            retv |= ret_for_file

    return retv
