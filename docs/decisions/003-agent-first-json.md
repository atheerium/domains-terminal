# ADR-003: Agent-First JSON Output

**Status**: Accepted  
**Date**: 2026-06-29

## Context

The primary consumers of this tool's output are LLM agents (OpenCode, Claude Code, Hermes). Humans are secondary. This inverted the output format decision.

## Decision

Every command outputs JSON by default with a standard envelope:

```json
{
    "status": "ok" | "error",
    "command": "filter",
    "data": [...],
    "meta": { "count": 5, "rules": ["brandable"] }
}
```

Pass `--format table` for human-readable tabular output.

## Alternatives Considered

- **Human-first**: Pretty tables by default → agents need `--format json` → inconsistent
- **Raw dicts printed**: No error handling, no metadata — agents can't distinguish success from failure

## Consequences

Positive:
- Agents parse one consistent structure — no screen-scraping, no string parsing
- `status` field means agents always check for errors before consuming data
- `meta` carries context (counts, sources, processing time) without polluting data

Negative:
- Two output paths to maintain (JSON + table) — every new command must support both
- Table output is less polished than a dedicated library like `rich` would provide (acceptable for v1)
