---
summary: _detect_trailing now returns a sealed union (Noop | AppendLf | Truncate) consumed by an exhaustive match in fix_file; the magic strings and dummy offset are gone, behavior unchanged.
---

# Design: Type the EOF-action seam

## Summary

`_detect_trailing` returns `tuple[str, int]` with magic strings
`"none"`/`"append_lf"`/`"truncate"` plus an offset that is meaningful only for
`truncate`; `fix_file` branches on those strings with a comment-only
`else: # truncate`. The seam is checker-invisible (a typo in a string is not
caught) and models a sum with a product (the dummy offset rides on every
variant). This change replaces the seam with a sealed union of frozen
dataclasses consumed by an exhaustive `match`. Behavior is unchanged.

## Goal

Make the detect→apply contract explicit and exhaustively type-checked, and make
illegal states unrepresentable (the offset lives only where it applies). No
change to what the tool does.

## Design

### Sealed union

```python
@dataclasses.dataclass(frozen=True)
class Noop: ...        # empty, or already ends with exactly one terminator
@dataclasses.dataclass(frozen=True)
class AppendLf: ...    # lacks a trailing newline; append one LF
@dataclasses.dataclass(frozen=True)
class Truncate:        # excess trailing newlines; truncate to `offset` (0 = empty)
    offset: int

_EofAction = Noop | AppendLf | Truncate
```

The `offset` exists only on `Truncate`, where it is meaningful — the dummy `0`
on the old `none`/`append_lf` tuples is gone. The variant classes are internal
to `fixer.py` (not part of the public `fix_file`/`fix_directory` contract); the
union alias is private (`_EofAction`).

### Consumption

`_detect_trailing(file_obj) -> _EofAction` returns `Noop()` / `AppendLf()` /
`Truncate(n)` where it used to return the string tuples. `fix_file` consumes it
with an exhaustive `match`:

```python
match _detect_trailing(file_obj):
    case Noop():
        return False
    case AppendLf():
        if not check:
            file_obj.seek(0, os.SEEK_END)
            file_obj.write(b"\n")
        return True
    case Truncate(offset):
        if not check:
            file_obj.seek(offset)
            file_obj.truncate()
        return True
```

### Exhaustiveness without a wildcard

No `case _` and no `assert_never` are needed. `fix_file` is typed `-> bool`, so
if a future variant is added to `_EofAction` and left unhandled, the `match`
falls through and the function can implicitly return `None`, which ty rejects
(`invalid-return-type`). Verified against the project's ty 0.0.42:

- all three cases handled → clean;
- a fourth, unhandled variant → `error[invalid-return-type]: Function can
  implicitly return None, which is not assignable to return type bool`.

This avoids `typing.assert_never` / `typing.Never` (both 3.11+, and the project
floors at 3.10 with no `typing_extensions` dependency). The typed seam is
therefore *leaner* than the string version — no helper, no new pragmas.

## Scope

- `_detect_trailing`'s internal byte-scan and its final
  `raise AssertionError("unreachable")  # pragma: no cover` are unchanged — that
  fallthrough is about the byte logic, not the seam.
- `_is_binary`, `fix_directory`, `main()`, and `discovery` are untouched.
- The public interfaces `fix_file(file_obj, *, check) -> bool` and
  `fix_directory(...)` keep their exact signatures and behavior.

## Testing

Behavior is preserved, so existing tests stay green unchanged. One **new** test
is required for coverage: the refactor splits the single old `if not check:`
into a per-case guard, so the `Truncate`-under-`--check` branch needs its own
test (`_run(b"abc\n\n\n", check=True)` → returns `True`, writes nothing).
Without it, coverage drops below the enforced 100%.

## Architecture promotion

`architecture/eof-normalization.md` describes the action model as
"none / append_lf / truncate"; update it to the typed sealed union
(`Noop` / `AppendLf` / `Truncate(offset)`) and the exhaustive `match`.

## Risk

- **Low.** Behavior-preserving, single-file, statically verified. The main
  watch-item is coverage: the split `if not check` needs the added truncate
  check-mode test, included above.
