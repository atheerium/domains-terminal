# Feature Inventory

Complete capability inventory for Domains Terminal. Use this to know what exists, what works, and what needs building.

## Legend

| Icon | Meaning |
|------|---------|
| ✅ | Implemented and tested |
| ⚠️ | Implemented but unwired from CLI |
| ❌ | Not implemented |

---

## 1. CLI Commands

All output JSON by default (`{status, command, data, meta}`). Pass `--format table` for tabular output.

| Command | Purpose | Parameters | Status |
|---------|---------|------------|--------|
| `dt init` | Create database and schema | — | ✅ Real |
| `dt available` | Check domain availability (DNS/WHOIS) | `TARGET` (domain or file), `--method simple|full` | ✅ Real |
| `dt trademark` | Check trademark via Signa.so | `TARGET` (domain or file), `--offices uspto,euipo,wipo` | ✅ Real |
| `dt scrape` | Fetch domains from providers | `--source` (dropcatch/expireddomains/namebio), `--tld`, `--format` | ❌ Stub — returns hardcoded domains |
| `dt filter` | Apply filter rules | `--rules` (comma-separated), `--format` | ❌ Stub — returns all domains unfiltered |
| `dt score` | Score domains | `--rules` (comma-separated), `--format` | ❌ Stub — returns zero scores |
| `dt enrich` | Add external data | `--source` (namebio), `--format` | ❌ Stub — no-op |
| `dt appraise` | Appraise domains | `--limit`, `--min-score`, `--format` | ❌ Stub — returns nothing |
| `dt top` | List top domains | `--limit`, `--min-score`, `--sort`, `--format` | ❌ Stub — empty output |
| `dt stats` | Database statistics | `--format` | ❌ Stub — zero counts |
| `dt pipeline` | Run full pipeline | `--sources`, `--rules`, `--format` | ❌ Stub — runs all stubs sequentially |

## 2. Filter Rules

Each rule is a standalone predicate function. The `Filter` class composes them into pipelines.

| Rule | Parameters | Logic | Status |
|------|-----------|-------|--------|
| `brandable` | — | 6-12 chars, no numbers/hyphens, pronounceable, vowel ratio 0.25–0.6 | ✅ Tested |
| `short` | `max_length` (default 8) | Name part ≤ max_length | ✅ Tested |
| `no_numbers` | — | No digit characters | ✅ Tested |
| `no_hyphens` | — | No hyphen characters | ✅ Tested |
| `tld` | `allowed` (default `["com"]`) | TLD in allowed list | ✅ Tested |
| `age` | `min_age` (default 5) | Checks `archive_year` metric in DB | ⚠️ Needs metric data |
| `traffic` | `min_monthly` (default 100) | Checks `monthly_visits` metric in DB | ⚠️ Needs metric data |
| `no_double_letters` | — | No consecutive identical letters | ✅ Tested |
| `vc_ratio` | `min_ratio` (0.25), `max_ratio` (0.75) | Vowel/consonant ratio in range | ✅ Tested |
| `starts_with_letter` | — | First char is alphabetic | ✅ Tested |
| `ends_with_letter` | — | Last char is alphabetic | ✅ Tested |
| `min_length` | `min_length` (default 3) | Name part ≥ min_length | ✅ Tested |

**Tests**: 22/22 passing.

## 3. Scoring Dimensions

Each dimension returns a `Score` model (0–100). Composite = weighted average.

| Dimension | Weight | Logic | Status |
|-----------|--------|-------|--------|
| `brandability` | 25% | Length curve + penalties for numbers/hyphens + vowel density + dictionary bonus | ✅ Tested |
| `mnemonic` | 15% | Double letters, alternating C-V patterns, assonance, repetition | ✅ Tested |
| `length` | 20% | Bell-curve centered on 6-8 chars, steep drop outside 3-12 | ✅ Tested |
| `tld_value` | 15% | Lookup table: .com=100, .io=80, .org=70, .net=65, .co=60, .ai=70, .app=55, .dev=50, .xyz=20, others=10 | ✅ Tested |
| `keywords` | 15% | Dictionary word match (200+ word set), multi-word bonus | ✅ Tested |
| `pronounceable` | 10% | Vowel ratio scoring, consonant cluster penalties | ✅ Tested |

**Tests**: 19/19 passing.

## 4. Appraisal Engine

| Capability | Logic | Status |
|-----------|-------|--------|
| **Comp-based estimate** | Median of comparable sales × multipliers (retail 1.3×, wholesale 0.6×) | ✅ Tested |
| **Fallback estimate** | Rule-of-thumb by TLD tier + domain length (no comps needed) | ✅ Tested |
| **Score adjustment** | Composite score multiplies retail range | ✅ Tested |
| **Buy recommendation** | Wholesale > current_price with sufficient confidence | ✅ Tested |
| **Confidence** | 0.0–1.0: high with ≥3 comps + high-score confidence, low without comps | ✅ Tested |
| **Reason string** | Human-readable explanation of valuation | ✅ Tested |

**Comp matching**: Same TLD, similar length (±3 chars), keyword overlap. Ordered by relevance.

**Tests**: 4/4 passing.

## 5. Providers

### DropCatch (`providers/dropcatch.py`)

| Feature | Status | Details |
|---------|--------|---------|
| OAuth2 auth | ✅ Real | Client ID + secret → bearer token; cached to `~/.config/domains-terminal/token.json` |
| `get_auctions()` | ✅ Real | Fetches live auctions with filters (TLD, bid range, page) |
| `get_backorders()` | ✅ Real | Active backorder listings |
| `bulk_download()` | ✅ Real | Bulk auction data download |
| Env vars | Required | `DROPCATCH_CLIENT_ID`, `DROPCATCH_CLIENT_SECRET` |

### ExpiredDomains (`providers/expireddomains.py`)

| Feature | Status | Details |
|---------|--------|---------|
| `get_expiring()` | ✅ Real | BS4 scrape of expiring domain lists |
| `get_expired()` | ✅ Real | Recently deleted domain lists |
| Auth | Optional | Free account for some sections |
| Env vars | Optional | `EXPIREDDOMAINS_USERNAME`, `EXPIREDDOMAINS_PASSWORD` |

### NameBio (`providers/namebio.py`)

| Feature | Status | Details |
|---------|--------|---------|
| `search_sales()` | ✅ Real | API search (preferred) with BS4 fallback |
| `get_comps()` | ✅ Real | Comparable sales lookup by domain |
| Auth | Optional | API key for higher rate limits |
| Env vars | Optional | `NAMEBIO_API_KEY` |

## 6. Storage

| Table | Purpose | CRUD |
|-------|---------|------|
| `domains` | Domain records, source, price, status | `insert_domain`, `get_domains`, `get_domain` |
| `metrics` | Key-value per-domain metrics | `insert_metric` |
| `scores` | Scoring dimension results | `insert_score`, `get_scores` |
| `appraisals` | Valuation records | `insert_appraisal` |
| `sales_cache` | NameBio comparable sales | Read via `execute` |
| `events` | Domain lifecycle audit log | `insert_event` |

**Engine**: SQLite (stdlib `sqlite3`), ACID, auto-init via `init()`.

## 7. Data Models (Pydantic)

| Model | Key Fields |
|-------|-----------|
| `Domain` | domain, source, tld, length, word_count, contains_numbers, seen_at, current_price, auction_id |
| `Score` | domain, rule, score (0–100), confidence |
| `Appraisal` | domain, retail_min/max, wholesale_min/max, buy_recommendation, confidence, reason |
| `Sale` | keyword, domain, sale_price, venue, sale_date |
| `Event` | domain, event_type, details |
| `Metric` | domain, metric_type, value |
| `PipelineResult` | status, command, data, meta |

## 8. Output Format

**JSON (default)**:
```json
{
    "status": "ok",
    "command": "filter",
    "data": [...],
    "meta": {"count": 5, "rules": ["brandable"]}
}
```

**Table** (`--format table`): Tabular display via `rich` library.

## 9. Tests (51 passing)

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_filter.py` | 22 | All 12 rules + rule registry |
| `tests/test_scoring.py` | 19 | All 6 dimensions + composite engine |
| `tests/test_appraise.py` | 4 | With/without comps, buy rec, score influence |

## 10. What's Wired vs Unwired

```
                    ┌─────────────────────────────────┐
                    │         CLI (click)              │
                    │  dt scrape, filter, score, etc.  │
                    └──────────┬──────────────────────┘
                               │ ALL STUBS ❌
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                     ▼
   ┌───────────┐       ┌───────────┐        ┌──────────────┐
   │ providers/│       │  core/    │        │   storage    │
   │ dropcatch │       │ filter.py │        │   SQLite     │
   │ expired-  │       │ scoring.py│        │   ACID ✅    │
   │ domains   │       │ appraise  │        └──────────────┘
   │ namebio   │       │ .py       │
   │ REAL ⚠️   │       │ REAL ✅   │
   └───────────┘       └───────────┘
```

**Key gap**: CLI commands use `# --- stub ---` inline data instead of calling the real engines and providers. Unwiring this is the highest-priority task.

## Availability Check (`core/availability.py`)

| Method | Logic | Status |
|--------|-------|--------|
| `check_simple(domain)` | DNS A/AAAA/NS lookup — if NXDOMAIN, available | ✅ Tested |
| `check_full(domain)` | WHOIS query — extracts registrar, dates, nameservers | ✅ Tested |
| `check_bulk(domains, method)` | Runs fast or thorough check per domain | ✅ Tested |

**Tests**: 8/8 passing.

## Trademark Check (`providers/signa.py`)

| Method | Logic | Status |
|--------|-------|--------|
| `check_trademark(domain, api_key, offices)` | Signa.so API POST, risk classification (high/medium/low) | ✅ Tested |
| `check_trademark_bulk(domains, api_key, offices)` | Sequential checks with 0.5s rate-limit | ✅ Tested |
| TARGET_CLASSES | [9, 35, 36, 38, 39, 41, 42, 45] | ✅ |
| ACTIVE_STATUSES | published, opposition_period, registered | ✅ |

**Tests**: 9/9 passing.
