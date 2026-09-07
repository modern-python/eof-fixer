# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`eof-fixer` is a single-purpose CLI: it walks a directory tree and rewrites every text file it
visits to end with exactly one line terminator. [`CONTEXT.md`](CONTEXT.md) opens with what it does
and owns the vocabulary — read it before naming a concept in code, a test name, or an issue title.

## Commands

`just` (task runner) and `uv` (package manager). The [`justfile`](justfile) is the source of truth —
`just --list`, or read it. The one thing it does not say: a `ty` suppression is written
`# ty: ignore`, never `# type: ignore`.

## Architecture

Three modules under `eof_fixer/`, each named for what it does and short enough to read whole:
`discovery.py` decides which files are visited, `fixer.py` decides and applies the change,
`main.py` is the CLI adapter. Read them.

### Testing patterns

The three layers are tested at three surfaces: byte-level behaviour against `io.BytesIO`, walk and
orchestration behaviour against a `tmp_path` tree, and only the argparse/exit-code adapter through
`main()`.

## Workflow

Real work **not scheduled** becomes a GitHub issue.

Every link in `README.md` must be absolute: `https://github.com/modern-python/<repo>/blob/main/<path>`,
or `.../tree/main/<path>` for a directory. Never a relative path: `README.md` is also the PyPI long
description, and PyPI does not rewrite relative links, so a relative one 404s on the package page.

An invariant is a test whose name is the claim, with a docstring opening `INVARIANT:` and a second
paragraph naming **what breaks it** — design rationale, not a report of what this one test catches.
