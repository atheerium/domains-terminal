# Database Schema

**File**: `storage.py` → `~/.domains-terminal/domains.db`  
**Engine**: SQLite 3 (stdlib `sqlite3`)  
**Design**: Single source of truth — no caching layer, no ORM.

## Tables

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

Each row is one domain name, uniquely identified by the domain string.  
`source` tracks where it came from (e.g. `dropcatch:auction`, `expireddomains:expiring`).  
`current_price` is the current bid/price from the source.  
`raw_data` stores the full provider response JSON for debugging.

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

Key-value store per domain.  
`metric_type` values: `archive_year`, `monthly_visits`, `backlinks`, `domain_authority`, etc.  
This table is populated by the `enrich` command.

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

One row per scoring dimension per domain.  
`rule` names: `brandability`, `mnemonic`, `length`, `tld_value`, `keywords`, `pronounceable`.  
`score` is 0–100. `confidence` is 0.0–1.0.

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

Historical domain sales used for comparable analysis.  
Populated by `enrich --source namebio`.  
Consumed by the appraisal engine for comps.

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

Audit log for domain lifecycle events: `seen`, `scored`, `appraised`, `bought`, `sold`.

## Usage Rules

- **Never write to SQLite directly** — always go through `Storage` methods
- **Never assume a table exists** — call `storage.init()` first
- **Never mutate models** after inserting — insert new versions with updated timestamps
- **Never delete rows** — use status flags (`is_available`, `status`) instead
