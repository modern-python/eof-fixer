# Project Context for Agents

## Project Overview
This is a Python project that implements an "End Of File Fixer" - a tool that ensures files end with exactly one newline character. The tool scans files in a directory and automatically adds or removes newlines at the end of files to maintain consistent formatting.

Despite the project name, the description in `pyproject.toml` mentions "Implementations of the Circuit Breaker" which appears to be incorrect or outdated.

### Key Technologies
- **Language**: Python 3.10+
- **Dependencies**: 
  - `pathspec` for gitignore pattern matching
- **Development Tools**:
  - `uv` for package management and building
  - `ruff` for linting and formatting
  - `mypy` for type checking
  - `pytest` for testing
  - `just` as a command runner

### Architecture
The project follows a simple CLI tool structure:
- Main entry point: `end_of_file_fixer/main.py`
- CLI interface using `argparse`
- File processing logic in `_fix_file()` function
- Integration with `.gitignore` patterns via `pathspec`

## Building and Running

### Setup
```bash
# Install dependencies
just install
```

### Development Commands
```bash
# Run linting and type checking
just lint

# Run tests
just test

# Run tests with arguments
just test -v

# Format code
just lint  # Includes auto-formatting
```

### Using the Tool
```bash
# Fix files in a directory (modifies files)
python -m end_of_file_fixer.main /path/to/directory

# Check files in a directory (dry run)
python -m end_of_file_fixer.main /path/to/directory --check
```

Or using the installed script:
```bash
# Fix files
end-of-file-fixer /path/to/directory

# Check files
end-of-file-fixer /path/to/directory --check
```

## Development Conventions

### Code Style
- Line length: 120 characters
- Strict type checking with mypy
- Ruff linting with specific rule exceptions (see pyproject.toml)
- No mandatory docstrings (D1 ignored)

### Testing
- Uses pytest framework
- Tests should be placed in the `tests/` directory
- Follow standard pytest naming conventions (`test_*.py` files, `test_*` functions)

### Project Structure
```
end-of-file-fixer/
├── end_of_file_fixer/     # Main package
│   ├── __init__.py        # Package initializer
│   └── main.py            # Main CLI implementation
├── tests/                 # Test files
│   └── test_dummy.py      # Sample test file
├── pyproject.toml         # Project configuration
├── Justfile               # Command definitions
├── README.md              # Project description
└── .gitignore             # Git ignore patterns
```

### Dependency Management
- Uses `uv` for fast dependency resolution and installation
- Dependencies defined in `pyproject.toml`
- Development dependencies in `[dependency-groups].dev`

### CI/CD
- Linting and type checking enforced in CI
- Publishing handled via `just publish` command
