---
status: accepted
summary: Keep the Python 3.10 floor and vendor a local _assert_never for match exhaustiveness; revisit using stdlib typing.assert_never when 3.10 EOLs (2026-10-31).
---

# Keep 3.10; vendor _assert_never until 3.10 EOL

**Decision:** Support Python 3.10 for now and enforce match exhaustiveness with a
locally-defined `_assert_never(value: NoReturn) -> NoReturn`, rather than
`typing.assert_never` (3.11+) or a `typing_extensions` dependency.

## Context

Typing the EOF-action seam wanted an exhaustive `match` pinned at the match site.
`typing.assert_never` is 3.11+ (verified absent on 3.10); the package floors at
`>=3.10` and CI tests 3.10. `typing_extensions` is only a marker-limited
transitive (absent on >=3.13), so using it would mean a new direct dependency.

## Decision & rationale

`typing.assert_never`'s body is ~2 lines; vendoring it as `_assert_never` gives
identical runtime behavior and the same ty exhaustiveness enforcement on
3.10-3.14 with zero dependencies. Dropping 3.10 now (its security-only EOL is
2026-10-31, ~4 months out) would be a breaking, outward-facing change to save a
few lines - not worth it while 3.10 is still supported. The vendored helper is
the reversible choice; dropping the floor is not.

## Revisit trigger

When Python 3.10 reaches end-of-life (2026-10-31): consider bumping
`requires-python` to `>=3.11`, dropping the 3.10 classifier/CI entry, and
replacing `_assert_never` with `from typing import assert_never`. That bump is a
breaking change warranting a minor/major release and a release note.
