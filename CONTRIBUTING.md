# Contributing to Domains Terminal

## Hard Rules (For All Agents)

These rules apply to every change, regardless of who or what makes it.

### Output Contract
- **Every command MUST output `{status, command, data, meta}`** — this is the contract all agents depend on
- **JSON is default, `--format table` for humans** — never reverse this
- **`status` must be `"ok"` or `"error"`** — no other values, no missing field

### Code Structure
- **One responsibility per module** — no `utils.py` junk drawers. Split when a file exceeds 400 lines.
- **Engine never imports CLI** — `core/` and `providers/` must not import `click` or reference `cli.py`
- **All inter-module data uses Pydantic models** — never pass `Dict[str, Any]` across module boundaries
- **Every public function has type hints** — no untyped parameters, no `Any` unless unavoidable
- **Every module starts with a contract block** — see existing modules for the pattern
- **No `# type: ignore`, `@ts-ignore`, or `as any`** — fix the type error

### Data
- **Storage is the single source of truth** — no in-memory caches, no global state that can be lost
- **Never write to SQLite directly** — always use `Storage` methods
- **Never delete rows** — use `status` or `is_available` flags instead

### Changes
- **One logical change per PR** — a new provider? One PR. A bug fix? Another PR.
- **Test before and after** — run `pytest tests/ -v` before committing
- **Update docs with every change** — if you add a provider, update `docs/providers.md`
- **Update ROADMAP.md** — move items from backlog to current sprint, mark completed
- **Update CHANGELOG.md** — add entry under the current version

### Dependencies
- **Prefer stdlib over PyPI** — `sqlite3`, `json`, `pathlib`, `dataclasses` before adding packages
- **No new dependencies without discussion** — each dep is a maintenance burden

## Development Setup

```bash
git clone https://github.com/atheerium/domains-terminal.git
cd domains-terminal
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
dt init
```

## Project Structure

```
domains-terminal/
├── domains_terminal/
│   ├── cli.py              # Click CLI (thin wrapper — no business logic)
│   ├── models.py           # Pydantic models
│   ├── storage.py          # SQLite CRUD
│   ├── utils.py            # Output formatting, helpers (pure functions)
│   ├── core/
│   │   ├── filter.py       # Filter predicates
│   │   ├── scoring.py      # Scoring engine
│   │   └── appraise.py     # Valuation engine
│   └── providers/
│       ├── dropcatch.py    # DropCatch API v2
│       ├── expireddomains.py
│       └── namebio.py
├── docs/
│   ├── architecture.md     # High-level architecture
│   ├── database.md         # Schema reference
│   ├── pipeline.md         # Pipeline flow
│   ├── providers.md        # Provider patterns
│   └── decisions/          # ADRs
├── tests/                  # Pytest test suite
├── scripts/                # Utility scripts
├── prompts/                # LLM prompts used internally
├── AI_CONTEXT.md           # Agent briefing (READ THIS FIRST)
├── ROADMAP.md              # Current priorities
├── CHANGELOG.md            # Release history
├── CONTRIBUTING.md         # This file
└── pyproject.toml
```

## Adding a New Provider

1. Create `domains_terminal/providers/myprovider.py`
2. Add module contract at top
3. Implement a class with `fetch(*, persist=True, **kwargs) -> List[Domain]`
4. Use Pydantic `Domain` models
5. Add tests in `tests/test_providers.py`
6. Update `docs/providers.md`
7. Wire into `cli.py` if needed

## Adding a New Filter Rule

1. Add `rule_xxx(domain: Domain, ...) -> bool` in `core/filter.py`
2. Register in `_RULES` dict
3. Add test in `tests/test_filter.py`
4. Update `docs/pipeline.md`

## Adding a New Scoring Dimension

1. Add `score_xxx(self, domain: Domain) -> Score` in `core/scoring.py`
2. Add weight in `DEFAULT_WEIGHTS`
3. Add test in `tests/test_scoring.py`
4. Update `docs/architecture.md`

## Running Tests

```bash
# All tests
pytest tests/ -v

# Single file
pytest tests/test_filter.py -v

# By keyword
pytest -k "brandable" -v

# With coverage
pytest --cov=domains_terminal tests/ -v
```

## Code Style

```bash
# Format
black domains_terminal/ tests/

# Lint
ruff domains_terminal/ tests/

# Type check
mypy domains_terminal/
```

## Asking for Help

- `dt --help` — discover commands
- `cat AI_CONTEXT.md` — agent briefing
- `docs/` — architecture, schema, providers, pipeline
- Create an issue for questions that aren't answered by docs
