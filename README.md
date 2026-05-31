# End Of File Fixer

A command-line tool that ensures all your text files end with exactly one newline character.
This tool helps maintain consistent file formatting across your codebase by automatically adding or removing trailing newlines as needed.

## Why This Matters

Many POSIX systems expect text files to end with a newline character. Having consistent line endings:
- Prevents spurious diffs in version control
- Ensures proper concatenation of files
- Satisfies POSIX compliance
- Improves readability in terminal environments

## Features

- Automatically adds a newline to files that don't end with one
- Removes excess trailing newlines from files that have too many
- Respects `.gitignore` patterns to avoid processing unwanted files
- Works with all text file types
- Cross-platform compatibility (Windows, macOS, Linux)
- Dry-run mode to preview changes before applying them

## Installation

### Using uv

```bash
uv add eof-fixer
```

### Using pip

```bash
pip install eof-fixer
```

## Usage

### Basic Usage

To fix all files in the current directory and subdirectories:

```bash
eof-fixer .
```

To check which files would be modified without making changes:

```bash
eof-fixer . --check
```

## How It Works

The eof-fixer processes files in the following way:

1. **Files with no trailing newline**: Adds exactly one newline at the end
2. **Files with exactly one trailing newline**: Leaves unchanged
3. **Files with multiple trailing newlines**: Truncates to exactly one newline
4. **Empty files**: Left unchanged

### Examples

| Original File Content | After Processing |
|----------------------|------------------|
| `hello world`        | `hello world\n`  |
| `hello world\n`      | `hello world\n`  |
| `hello world\n\n\n`  | `hello world\n`  |
| `` (empty file)      | `` (unchanged)   |

> **Note on line endings:** when appending a missing terminator, eof-fixer always
> writes an LF (`\n`), regardless of the existing line-ending style of the file.
> A file that otherwise uses CRLF or CR will end up with a mixed terminator on
> its last line. This matches the behavior of pre-commit's `end-of-file-fixer`.
> Files that already end with a single CRLF, CR, or LF are left untouched.

## Configuration

The tool automatically respects patterns in your `.gitignore` file, so it won't process files that are ignored by Git. Only the `.gitignore` at the root of the supplied path is consulted; nested `.gitignore` files in subdirectories are not read. Additionally, it always ignores:
- `.git` directories
- `.cache` and `.uv-cache` directories (used by uv)
- Binary files (detected by null bytes in the first 1024 bytes)

## Exit Codes

- `0`: No files needed fixing.
- `1`: At least one file needed fixing. In `--check` mode no changes are written;
  in the default (fix) mode the files have been rewritten in place. The non-zero
  exit in fix mode is intentional so the tool can be used as a pre-commit or CI
  gate — re-run after the fix and the exit code returns to `0`.

## Development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) for dependency management

### Setup

```bash
# Clone the repository
git clone https://github.com/modern-python/eof-fixer.git
cd eof-fixer

# Install dependencies
just install
```

### Running Tests

```bash
# Run tests
just test
```

### Linting

```bash
# Run linting and formatting
just lint
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

The core file-fixing logic in this project is derived from the
[`end-of-file-fixer`](https://github.com/pre-commit/pre-commit-hooks/blob/main/pre_commit_hooks/end_of_file_fixer.py)
hook in [`pre-commit/pre-commit-hooks`](https://github.com/pre-commit/pre-commit-hooks),
which is also distributed under the MIT License. This project repackages that
logic as a standalone CLI with `.gitignore`-aware directory traversal so it can
be used outside of the pre-commit framework.

## Related Projects

- [pre-commit](https://pre-commit.com/) - A framework for managing and maintaining multi-language pre-commit hooks
- [editorconfig](https://editorconfig.org/) - Helps maintain consistent coding styles across different editors and IDEs

## Part of `modern-python`

Browse the full list of templates and libraries in
[`modern-python`](https://github.com/modern-python) — see the org profile for the
categorized index.
