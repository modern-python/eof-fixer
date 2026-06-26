---
summary: Fix behavior now lives behind eof_fixer/fixer.py (fix_file + fix_directory); main() is a thin adapter and tests target the interface instead of the argv/stdout/cwd harness.
---

# Design: Deepen the fix into `fixer.py`; `main()` becomes an adapter

## Summary

Today `main()` fuses three jobs — CLI parsing, the fix-loop, and `stdout`/exit
rendering — so the fix behavior has no interface of its own. Every one of the 16
tests reaches it through the process: swapping `sys.argv`, `sys.stdout`, and
`os.chdir` via a `_run_main_in` harness, even to assert pure byte-level facts
like "`\r\n\r\n` truncates to `\r\n`." This change extracts the EOF-fixing
capability into a deep module `eof_fixer/fixer.py` exposing two honest
interfaces, leaving `main()` a thin adapter. The interface becomes the test
surface.

## Goal

Move the test surface off the global-state harness onto a direct interface,
improving testability and locality. No change to *what* the tool does (which
files it fixes, the `Fixing` lines, the exit codes) — only *where the behavior
lives* and one non-semantic output-timing detail.

## Design

### New module `eof_fixer/fixer.py`

Owns the eof-normalization capability and the directory orchestration that
drives it:

```python
DEFAULT_EXCLUDES = (".cache", ".uv-cache")   # local named constant
_BINARY_SAMPLE_SIZE = 1024                    # local named constant

_is_binary(file_obj) -> bool                  # private internal (uses _BINARY_SAMPLE_SIZE)
_detect_trailing(file_obj) -> tuple[str, int] # private internal (unchanged)
fix_file(file_obj, *, check) -> bool          # public: fix one open file; True if (would be) fixed
fix_directory(root, *, check=False, extra_excludes=()) -> list[pathlib.Path]
```

`fix_directory` builds `[*DEFAULT_EXCLUDES, *extra_excludes]`, calls
`discovery.iter_text_files`, opens each yielded file (`rb` under `check`, else
`rb+`), runs `fix_file`, and returns the relative paths it fixed (or, under
`check`, would fix) in walk order. The file-level helpers `_is_binary` /
`_detect_trailing` / the old `_fix_file` move here from `main.py`; `fix_file` is
the de-underscored, `bool`-returning form of `_fix_file`.

### `main.py` becomes a thin adapter

```python
parse args (path, --check, --exclude)
if not path.is_dir(): parser.error(...)        # CLI-shaped, exit 2 — stays here
fixed = fix_directory(path, check=args.check, extra_excludes=args.exclude or [])
for p in fixed: sys.stdout.write(f"Fixing {p}\n")
return 1 if fixed else 0
```

`main()` no longer imports `os`/`IO`; it holds only argparse, the `is_dir`
guard, the render loop, and the exit code.

## Key decisions (from the design conversation)

- **Return shape:** `list[pathlib.Path]`, walk order — both the `Fixing` lines
  and the exit code derive from it. No `FixReport` wrapper (YAGNI); promote
  later if a counts consumer appears.
- **Silent module, batch output:** `fix_directory` touches no `stdout`; `main()`
  renders after the walk. Output shifts streaming → batch — same lines, order,
  and exit code; only timing differs. Acceptable for a fast CI/pre-commit gate.
- **Default-skip policy lives in `fixer.py`** (`DEFAULT_EXCLUDES`), so tests get
  production defaults for free and `main()` carries no behavior policy.
  `extra_excludes` means "user additions"; `.git` stays inside `discovery`.
- **Constants stay local**, no central settings module — see
  `planning/decisions/2026-06-26-no-central-settings-module.md`.
- **Absorbs the open-mode "leak"** (review Candidate 3): the open and the fix
  loop now live in one module, so no rule crosses a `main` ↔ `_fix_file` seam.
- The stringly-typed `_detect_trailing` seam (review Candidate 2) is **left
  as-is** — out of scope for this change.

## Testing — three layers

- **Content** → `fix_file(BytesIO(...), check=...)`: CRLF/CR/BOM/null-byte/
  perfect-unchanged, no filesystem.
- **Orchestration** → `fix_directory(tmp_path, ...)`: gitignore respected,
  binary skipped, symlink, `--exclude`, check-vs-fix, cwd-independence — assert
  on the returned list and on-disk bytes.
- **Adapter** → keep ~2 through `main()`: path-rejection (exit 2) and one test
  that `main()` renders `Fixing` lines + the exit code from the list.
  `_run_main_in` shrinks to serve only these.

## Architecture promotion

In the implementing PR: `architecture/eof-normalization.md` (capability now
behind `fixer.fix_file` / `fix_directory`) and `architecture/cli.md` (`main()`
is an adapter over `fix_directory`).

## Risk

- **Output timing change (streaming → batch):** non-semantic; noted in the
  release notes when next shipped.
- **Test migration churn:** large but mechanical; the full suite must stay green
  at each task. Coverage stays 100%.
