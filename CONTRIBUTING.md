# Contributing to Domains Terminal

## Quick Start

```bash
git clone https://github.com/atheerium/domains-terminal.git
cd domains-terminal
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
dt init
dt scrape --format table
```

## Project Structure

```
domains-terminal/
├── domains_terminal/
│   ├── __init__.py          # Package metadata
│   ├── cli.py               # Click CLI entry point
│   ├── models.py            # Pydantic models
│   ├── storage.py           # SQLite CRUD
│   ├── utils.py             # Output formatting, helpers
│   ├── core/
│   │   ├── filter.py        # Filter predicates + registry
│   │   ├── scoring.py       # 6-dimension scoring engine
│   │   └── appraise.py      # Comparable-sales valuation
│   └── providers/
│       ├── dropcatch.py     # DropCatch API v2
│       ├── expireddomains.py# ExpiredDomains.net scraper
│       └── namebio.py       # NameBio sales data
├── tests/                    # Pytest test suite
├── ARCHITECTURE.md           # System design docs
├── AGENT.md                  # AI agent collaboration guide
├── CONTRIBUTING.md           # This file
└── pyproject.toml            # Build/install config
```

## Code Style

- **Formatter**: `black` (default config)
- **Linter**: `ruff` (default config)
- **Type hints**: Required on all public functions
- **Docstrings**: Google/NumPy style on public APIs
- **Imports**: stdlib → third-party → project (alphabetical groups)
- **No `as any` or `# type: ignore`**: Type errors must be fixed, not suppressed

## PR Guidelines

1. **One change per PR**: A new provider? Open one PR. A bug fix? Another PR.
2. **Test before submitting**: `pytest tests/` passes (or note pre-existing failures)
3. **JSON contract preserved**: Every command must still output `{status, command, data, meta}`
4. **No speculative features**: Don't add what wasn't asked
5. **No AI-generated slop**: Keep functions small, comments meaningful, names descriptive

## Feature Requests

Open an issue describing:

- What the feature does
- Example CLI usage and expected output
- Any providers/rules/scoring it involves
- Why it fits Domains Terminal

## Bug Reports

Include:

- The exact command that failed
- Full output (with `--format json`)
- Expected vs actual behavior
- Python version (`python --version`)

## Adding a New Provider

See [AGENT.md](AGENT.md) for the pattern. Generally:

1. Create `domains_terminal/providers/yourprovider.py`
2. Wire into `cli.py` if it needs its own subcommand
3. Test with `pytest`
4. Run `pip install -e . && dt <command> --format table`

## Adding a New Command

1. Add a Click command function in `cli.py`
2. Use the `_output()` helper for formatting
3. Add the `--format` option supporting both `json` and `table`
4. Register in `todowrite` planning when multi-step

## Running Tests

```bash
pytest tests/ -v
pytest tests/test_filter.py -v  # Single file
pytest -k "brandable" -v        # Keyword match
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
