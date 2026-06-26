import argparse
import pathlib
import sys

from eof_fixer.fixer import fix_directory


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
    if not path.is_dir():
        parser.error(f"path is not a directory: {path}")

    fixed = fix_directory(path, check=args.check, extra_excludes=args.exclude or [])
    for relative_path in fixed:
        sys.stdout.write(f"Fixing {relative_path}\n")
    return 1 if fixed else 0
