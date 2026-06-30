# Domains Terminal Architecture

## Overview

A modular CLI suite for domain flipping. One package, many subcommands. All structured output.

```
dt                          # Alias for domains-terminal
dt scrape        → fetch from sources (DropCatch, ExpiredDomains, etc.)
dt filter        → rule-based filtering
dt score         → multi-dimension scoring
dt enrich        → add metrics (Archive, NameBio, WHOIS)
dt appraise      → valuation with comparable sales
dt top           → show best opportunities
dt stats         → database statistics
dt pipeline      → full scrape → filter → score → appraise
```

## Design Principles

1. **One source of truth**: SQLite at `~/.domains-terminal/domains.db`
2. **Structured data everywhere**: JSON output for LLM agents
3. **Composable commands**: Unix philosophy, pipe-friendly
4. **Extensible by design**: Add providers, rules, and scoring dimensions without touching the CLI
5. **Human-friendly when needed**: `--format table` for terminal users

## Module Map

| File | Purpose | Modify When... |
|------|---------|---------------|
| `cli.py` | Click CLI entry point (9 commands) | Adding a new command or flag |
| `models.py` | Pydantic models (Domain, Score, Appraisal...) | Adding a new data type |
| `storage.py` | SQLite CRUD operations | Adding a new query or table |
| `utils.py` | Output formatting, logging, helpers | Changing how output looks |
| `core/filter.py` | Filter predicates + registry | Adding a new filter rule |
| `core/scoring.py` | Scoring dimensions + engine | Adding a new scoring metric |
| `core/appraise.py` | Appraisal engine + comps analysis | Changing valuation logic |
| `providers/dropcatch.py` | DropCatch API v2 client | Fixing DropCatch integration |
| `providers/expireddomains.py` | ExpiredDomains.net scraper | Adding ExpiredDomains features |
| `providers/namebio.py` | NameBio sales data client | Adding sale data features |

## Database Schema

### domains
```sql
CREATE TABLE domains (
    domain TEXT PRIMARY KEY,
    source TEXT,
    tld TEXT,
    length INTEGER,
    word_count INTEGER,
    contains_numbers INTEGER,
    seen_at TEXT,
    drop_at TEXT,
    current_price REAL,
    end_time TEXT,
    auction_id TEXT,
    is_available INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',
    raw_data TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### metrics
```sql
CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT REFERENCES domains(domain),
    metric_type TEXT,
    value TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### scores
```sql
CREATE TABLE scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT REFERENCES domains(domain),
    rule TEXT,
    score INTEGER,
    confidence REAL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### appraisals
```sql
CREATE TABLE appraisals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT REFERENCES domains(domain),
    retail_min INTEGER,
    retail_max INTEGER,
    wholesale_min INTEGER,
    wholesale_max INTEGER,
    buy_recommendation INTEGER,
    confidence REAL,
    reason TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### sales_cache (NameBio)
```sql
CREATE TABLE sales_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT,
    domain TEXT,
    sale_price INTEGER,
    sale_date TEXT,
    venue TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### events
```sql
CREATE TABLE events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT,
    event_type TEXT,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## JSON Output Contract

Every command outputs this structure:

```json
{
    "status": "ok",
    "command": "scrape",
    "data": [...],
    "meta": {
        "count": 42,
        "source": "dropcatch"
    }
}
```

- `status`: `"ok"` or `"error"` — check first before parsing data
- `command`: which command produced the output
- `data`: array of result records
- `meta`: metadata about the operation

## Providers

- **DropCatch** (`providers/dropcatch.py`): API v2 with OAuth2, auto-refresh, bulk downloads
- **ExpiredDomains** (`providers/expireddomains.py`): BeautifulSoup scraper, optional login
- **NameBio** (`providers/namebio.py`): API + scrape fallback for sales data

## Core Modules

- **scoring.py**: 6-dimensional scoring engine (brandability, length, mnemonic, TLD, keywords, pronounceability)
- **appraise.py**: Comparable-sales valuation with buy recommendations
- **filter.py**: 12+ filter predicates with argument parsing

## Extension Patterns

### Adding a Provider

1. Create `domains_terminal/providers/myprovider.py`
2. Implement a class with methods returning `List[Domain]`
3. Optionally accept `persist: bool = True` to auto-save to storage
4. Wire into `cli.py` if it needs its own subcommand

### Adding a Filter Rule

1. Add `def rule_xxx(domain: Domain, ...) -> bool` in `core/filter.py`
2. Register in the `_RULES` dict with a short name
3. If the rule takes arguments, `_parse_rule()` handles `int/float/str` conversion automatically

### Adding a Scoring Dimension

1. Add `def score_xxx(self, domain: Domain) -> Score` in `core/scoring.py`
2. Add a weight to `DEFAULT_WEIGHTS`
3. The engine auto-discovers methods prefixed with `score_`
