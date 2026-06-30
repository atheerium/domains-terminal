# AI Context — Domains Terminal

> **Read this before making any changes.** This file is a high-signal briefing for any coding agent (OpenCode, Claude Code, Hermes, etc.) working on this project.

## Project Purpose

Domains Terminal is a modular CLI suite for domain flipping. It scrapes domain names from sources (DropCatch, ExpiredDomains, NameBio), scores/appraises them, and outputs structured JSON for LLM agent orchestration. It's designed to be extended by AI agents, not just humans.

**One-line**: Bloomberg Terminal for domain names.

## Current Architecture

```
┌─────────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  CLI (click)        │────▶│  Engine           │────▶│  Storage     │
│  domains_terminal/  │     │  core/            │     │  (SQLite)    │
│  cli.py             │     │  filter.py        │     │  storage.py  │
│                     │     │  scoring.py       │     │              │
│                     │     │  appraise.py      │     │  domains.db  │
│                     │     └──────────────────┘     └──────────────┘
│                     │              │
│                     │     ┌────────▼────────┐
│                     │     │  Providers       │
│                     │     │  providers/      │
│                     │     │  dropcatch.py    │
│                     │     │  expireddomains  │
│                     │     │  namebio.py      │
│                     │     └─────────────────┘
└─────────────────────┘
```

## Coding Conventions (HARD RULES)

| Rule | Why |
|------|-----|
| **Every command outputs JSON** | Agents parse JSON, not terminal output |
| **`status: "ok"` / `status: "error"`** | Check this first in data[0] |
| **One responsibility per module** | No `utils.py` junk drawers — each file does one thing |
| **Pydantic models everywhere** | Never pass raw dicts between modules |
| **Engine never imports CLI** | `core/` and `providers/` must be usable without click |
| **No `# type: ignore` or `as any`** | Fix type errors, don't suppress them |
| **Every public fn has type hints + docstring** | Agents need contracts to use them |
| **Every module starts with a contract block** | """Purpose: / Input: / Output: / Dependencies: / Side effects:""" |
| **Storage is the single source of truth** | No in-memory state that would be lost |
| **Tests before/after every change** | Run `pytest tests/ -v` |

## Key Data Models (`models.py`)

All modules exchange models from `domains_terminal.models`. Never pass raw dictionaries between engines.

```
Domain     → domain, source, tld, length, current_price, end_time, auction_id, ...
Score      → domain, rule, score (0-100), confidence
Appraisal  → domain, retail_min/max, wholesale_min/max, buy_recommendation
Sale       → keyword, domain, sale_price, venue
Event      → domain, event_type, details
Metric     → domain, metric_type, value
PipelineResult → status, command, data, meta
```

## Current Priorities (from ROADMAP.md)

1. Wire CLI `pipeline` to use real engine steps instead of stub data
2. Add DropCatch API credentials to env for provider auth
3. Write tests for all filter rules and scoring dimensions
4. Add unit tests in `tests/`

## Known Technical Debt

- CLI commands `scrape`, `filter`, `score`, `enrich`, `appraise`, `pipeline` use stub data — not wired to real engines
- DropCatch provider needs `DROPCATCH_CLIENT_ID` / `DROPCATCH_CLIENT_SECRET` env vars
- `dropcatch.py` has a config path at `~/.config/domains-terminal/` (migrated from old tools)
- No CI pipeline configured yet
- No pre-commit hooks

## "Do Not Change" Rules

- **Do not change the JSON output contract** — all agents depend on `{status, command, data, meta}`
- **Do not remove the `dt` alias** — it's the primary way agents invoke the tool
- **Do not change the database schema** without creating a migration plan and an ADR
- **Do not add new dependencies** without checking if stdlib can do the job
- **Do not put business logic in `cli.py`** — CLI is just a thin wrapper

## How to Run

```bash
# Install
cd domains-terminal && pip install -e ".[dev]"

# Initialize DB
dt init

# Run commands
dt scrape --source dropcatch --format table
dt filter --rules brandable,short --format json
dt score --rules brandability,length
dt top --limit 10

# Run tests
pytest tests/ -v

# Shell completion
eval "$(_DT_COMPLETE=zsh_source dt)"
```

## How to Add a Module

1. Create file in the appropriate directory (`core/`, `providers/`, etc.)
2. Add module contract at top (Purpose / Input / Output / Dependencies / Side effects)
3. Use Pydantic models, not dicts
4. Wire into CLI if it needs a command
5. Update `docs/architecture.md` 
6. Add tests in `tests/`
7. Update `ROADMAP.md`
8. Run the full test suite

## How to Get Help

- `dt --help` — list all commands
- `dt <command> --help` — command-specific help
- `docs/architecture.md` — full architecture
- `docs/database.md` — schema details
- `docs/providers.md` — provider patterns
- `docs/pipeline.md` — pipeline flow
- `docs/decisions/` — architecture decision records
