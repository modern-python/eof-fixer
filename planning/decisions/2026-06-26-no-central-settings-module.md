---
status: accepted
summary: Keep constants local to the module that owns the behavior they parameterize; no central settings/constants module until config becomes runtime-loaded.
---

# Constants stay local; no central settings module

**Decision:** Promote magic literals to named module-level constants in the
module whose behavior they parameterize. Do **not** introduce a central
`settings.py` / `constants.py`.

## Context

While deepening the fix behavior into `eof_fixer/fixer.py`, the question arose
of where defaults like `.cache` / `.uv-cache`, the `1024`-byte binary sample,
and the terminator bytes should live — co-located, or gathered into one
settings/constants module.

`discovery.py` already keeps `GITIGNORE_NAME` and `ALWAYS_PRUNE` as local
module-level constants. The remaining literals partition cleanly by capability:
`.git` / `.gitignore` → file discovery; `.cache` / `.uv-cache` default skips →
the fix capability; the binary-sample size and terminator bytes →
eof-normalization. None of them are user-tunable: there is no env var, config
file, or `[tool.eof-fixer]` section — they are fixed constants, not settings.

## Decision & rationale

A central module would group these by *type* (they are all constants) rather
than by *responsibility*, which hurts locality: reading `_is_binary` would mean
bouncing to `constants.py` for `1024` and back. Keeping each constant beside the
logic it governs — e.g. `DEFAULT_EXCLUDES = (".cache", ".uv-cache")` in
`fixer.py` — names the value without scattering the behavior, and mirrors the
pattern `discovery.py` already uses. This is a deliberate locality choice, not
an oversight, so future architecture reviews should not re-suggest a settings
module on the grounds that "the constants are scattered."

## Revisit trigger

Reopen when configuration becomes **runtime-loaded** — a config file,
environment variables, or a `[tool.eof-fixer]` pyproject section. At that point a
dedicated config/settings module that parses and validates that input is the
right home, and this decision no longer applies.
