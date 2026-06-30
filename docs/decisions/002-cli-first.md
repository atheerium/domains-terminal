# ADR-002: CLI-First Architecture

**Status**: Accepted  
**Date**: 2026-06-29

## Context

The tool needs a user interface. Options: CLI, Web UI, TUI, Python library.

## Decision

Use Click CLI as the primary (and initial) interface. Design the engine layer so it can later support a web API, TUI, or GUI without changes to business logic.

## Alternatives Considered

- **Web UI first**: Premature — CLI is faster to build, test, and iterate for an agent-driven tool
- **Python library only**: No entry point for quick exploration
- **TUI (Textual)**: Good but adds complexity — defer to v2

## Consequences

Positive:
- `dt --help` is self-documenting — agents can discover capabilities
- Piped output works naturally: `dt top --format json | jq '.data'`
- Engine is CLI-agnostic — `core/` never imports `click`
- Easy to test: `subprocess.run(["dt", "filter", ...])`

Negative:
- CLI is not visually rich — no progress bars, no interactive tables (acceptable for v1)
- Some operations (like interactive auth) feel less natural on CLI
