# Domains Terminal

> Bloomberg Terminal for domain flipping — scrape, score, appraise, and acquire premium domain names.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](pyproject.toml)

```bash
dt init              # Set up the database
dt scrape --source dropcatch   # Fetch domains from sources
dt filter --rules brandable,short --format table  # Apply filters
dt pipeline --sources dropcatch --rules brandable,short  # Full pipeline
```

**Every command outputs JSON by default** — designed for LLM agent orchestration. Pass `--format table` for human-readable output.

## Quick Start

```bash
pip install domains-terminal

# Or from source:
git clone https://github.com/atheerium/domains-terminal.git
cd domains-terminal
pip install -e .

# Try it
dt init                  # Create ~/.domains-terminal/domains.db
dt scrape                # Fetch domains (stub data until credentials set)
dt filter --rules brandable,short --format table
dt score --rules brandability,length
dt appraise --limit 5
dt top --limit 10
```

## Commands

| Command | Description | JSON | Table |
|---------|-------------|------|-------|
| `dt init` | Create/initialize the SQLite database | ✅ | ✅ |
| `dt scrape` | Fetch domains from providers | ✅ | ✅ |
| `dt filter` | Apply named filter rules | ✅ | ✅ |
| `dt score` | Score domains across multiple dimensions | ✅ | ✅ |
| `dt enrich` | Add metrics (WHOIS, NameBio, Archive) | ✅ | ✅ |
| `dt appraise` | Estimate market value with comparable sales | ✅ | ✅ |
| `dt top` | Show top-scoring domains | ✅ | ✅ |
| `dt stats` | Database statistics | ✅ | ✅ |
| `dt pipeline` | Full scrape → filter → score → appraise pipeline | ✅ | ✅ |

## Architecture

```
┌─────────────┐    ┌────────────┐    ┌─────────────┐
│  Providers  │───▶│   Core     │───▶│   Storage   │
│  (scrape)   │    │(filter/    │    │  (SQLite)   │
│             │    │ score/     │    │             │
│ DropCatch   │    │ appraise)  │    │  domains.db │
│ ExpiredDoms │    │            │    │             │
│ NameBio     │    │            │    │             │
└─────────────┘    └────────────┘    └─────────────┘
       │                                        │
       └──────────── CLI (click) ───────────────┘
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design.

## Agent-Friendly Design

This tool is built for AI agents to:
- **Read and write**: All commands output structured JSON. No screen-scraping.
- **Extend**: Adding a new provider, filter rule, or scoring dimension takes ~20 lines.
- **Audit**: SQLite database is the single source of truth — query it directly.

See [AGENT.md](AGENT.md) for the agent collaboration guide.

## License

MIT
