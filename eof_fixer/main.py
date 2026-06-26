import argparse
import os
import pathlib
import sys
from typing import IO

from eof_fixer.discovery import iter_text_files


def _is_binary(file_obj: IO[bytes]) -> bool:
    current_pos = file_obj.tell()
    file_obj.seek(0)
    sample = file_obj.read(1024)
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


def _fix_file(file_obj: IO[bytes], check: bool) -> int:
    if _is_binary(file_obj):
        return 0

    action, offset = _detect_trailing(file_obj)
    if action == "none":
        return 0

    if not check:
        if action == "append_lf":
            # Needs this seek for windows, otherwise IOError
            file_obj.seek(0, os.SEEK_END)
            file_obj.write(b"\n")
        else:  # action == "truncate"
            file_obj.seek(offset)
            file_obj.truncate()

    return 1


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
