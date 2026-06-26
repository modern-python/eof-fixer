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
    if not last_character:
        return ("none", 0)
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

    raise AssertionError("unreachable")  # pragma: no cover  # noqa: EM101


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
