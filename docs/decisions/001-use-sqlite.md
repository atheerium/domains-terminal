# ADR-001: Use SQLite as Single Source of Truth

**Status**: Accepted  
**Date**: 2026-06-29

## Context

The tool needs to persist domain data, scores, appraisals, and sales history across sessions. Options considered: in-memory, JSON files, SQLite, PostgreSQL.

## Decision

Use SQLite (`sqlite3`, Python stdlib) as the single source of truth.

## Alternatives Considered

- **In-memory**: Lost on restart — unacceptable for a tool that accumulates data over days/weeks
- **JSON files**: Simple but no querying, no joins, race conditions on concurrent writes
- **PostgreSQL**: Overkill for a CLI tool — adds deployment dependency

## Consequences

Positive:
- Zero dependencies (stdlib `sqlite3`)
- ACID transactions, concurrent reads safe
- SQL query capability for analysis/auditing
- Single file — easy to backup, inspect, delete

Negative:
- No network access (cannot be used as a remote DB)
- Write concurrency limited (single-writer) — acceptable for CLI use
- Schema migrations need manual handling
