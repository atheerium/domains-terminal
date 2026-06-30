# Pipeline

## Flow

```
Scrape ──▶ Filter ──▶ Score ──▶ Enrich ──▶ Appraise ──▶ Top
  │           │          │          │            │          │
  ▼           ▼          ▼          ▼            ▼          ▼
 SQLite     SQLite     SQLite     SQLite       SQLite     stdout
```

## Stages

### 1. Scrape (`dt scrape`)
Fetches domain names from configured providers:
- **DropCatch**: Live auctions, backorders, bulk downloads
- **ExpiredDomains**: Expiring and recently expired lists
- **NameBio**: Historical sales data (for enrichment, not domain lists)

Each provider returns `List[Domain]`, which is persisted to `domains` table.

### 2. Filter (`dt filter`)
Applies rule predicates against each domain in the DB:
- `brandable`: 6-12 chars, pronounceable, no numbers/hyphens
- `short`: ≤8 characters
- `no_numbers`: no digits
- `no_hyphens`: no hyphens
- `tld`: allowed TLDs (default `com`)
- `age`: minimum registration age
- `traffic`: minimum monthly visits
- `no_double_letters`: no consecutive identical letters
- `vc_ratio`: vowel-consonant ratio within range
- `starts_with_letter`, `ends_with_letter`, `min_length`

Rules can take arguments: `tld:com,io`, `short:10`, `age:3`

### 3. Score (`dt score`)
Multi-dimensional scoring (0–100 per dimension):
- `brandability` (25%): length, hyphens, numbers, vowel density, dictionary match
- `mnemonic` (15%): double letters, alternating pattern, assonance
- `length` (20%): optimal 6-8 chars
- `tld_value` (15%): TLD quality lookup (.com=100, .xyz=20)
- `keywords` (15%): dictionary word match, multi-word bonus
- `pronounceable` (10%): vowel ratio, consonant clusters

### 4. Enrich (`dt enrich`)
Adds external data:
- NameBio sales history (comparable sales)
- Archive.org age data
- WHOIS info (future)
- Backlink/authority metrics (future)

### 5. Appraise (`dt appraise`)
Combined valuation:
- **With comps**: median(comparable prices) × multipliers
- **Without comps**: rule-of-thumb based on TLD, length, scores
- **Buy recommendation**: wholesale > current price with sufficient confidence

### 6. Top (`dt top`)
Query the highest-scored domains from the DB.

## Pipeline Command

```
dt pipeline --sources dropcatch --rules brandable,short
```

Runs all stages sequentially. Outputs summary of each step.
