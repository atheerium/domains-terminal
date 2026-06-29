# Agent Collaboration Guide for Domains Terminal

## Session Context

Before modifying any code, an agent should:

1. Read this file (AGENT.md) for collaboration patterns
2. Read ARCHITECTURE.md for the full design
3. Check the existing code in the relevant module
4. Run `dt --help` to see available commands
5. Run `dt stats` (after `dt init`) to see DB state

## JSON Output Contract

Every command outputs:

```json
{
    "status": "ok",
    "command": "filter",
    "data": [...],
    "meta": { "count": 5, "rules": ["brandable", "short"] }
}
```

- Always check `status` first
- `data` is always an array (empty `[]` on no results)
- `meta` contains context (counts, sources, rules applied)

## Data Flow

```
CLI (cli.py) → Core Modules (filter/score/appraise) → Storage (SQLite)
             → Providers (scrape sources)
```

SQLite at `~/.domains-terminal/domains.db` is the single source of truth.
Every provider can persist domains directly to storage. Every engine reads
from storage to enrich/score/appraise.

## How to Add a New Provider

1. Create `domains_terminal/providers/myprovider.py`
2. Pattern (duck-typed, no base class needed):

```python
from domains_terminal.models import Domain
from domains_terminal.storage import Storage

class MyProvider:
    def __init__(self, storage: Storage | None = None):
        self.storage = storage or Storage()

    def fetch(self, *, persist: bool = True, **kwargs) -> list[Domain]:
        domains = []  # ... fetch logic
        if persist:
            self.storage.init()
            for d in domains:
                self.storage.insert_domain(d.model_dump())
        return domains
```

3. Wire into `cli.py` if it needs a dedicated subcommand

## How to Add a Filter Rule

1. Add function in `domains_terminal/core/filter.py`:

```python
def rule_myfeature(domain: Domain, threshold: int = 5) -> bool:
    name = _name_part(domain.domain)
    return len(name) > threshold
```

2. Register in the `_RULES` dict:

```python
_RULES = {
    ...
    "myfeature": rule_myfeature,
}
```

3. Rules with arguments are auto-parsed by `_parse_rule()`. Use colon syntax:
   `dt filter --rules "myfeature:10"`

## How to Add a Scoring Dimension

1. Add method in `domains_terminal/core/scoring.py`:

```python
def score_myfeature(self, domain: Domain) -> Score:
    score_val = 50  # your logic here
    return Score(domain=domain.domain, rule="myfeature", score=score_val, confidence=0.7)
```

2. Add weight to `DEFAULT_WEIGHTS`:

```python
DEFAULT_WEIGHTS = {
    ...
    "myfeature": 0.10,
}
```

The engine auto-discovers `score_*` methods.

## Testing Patterns

```python
# tests/test_filter.py
from domains_terminal.models import Domain
from domains_terminal.core.filter import rule_brandable

def test_brandable_passes():
    d = Domain(domain="startup.io", tld="io")
    assert rule_brandable(d) is True
```

- Use `pytest` in `tests/` directory
- Test with Domain objects (simple to construct)
- Test filter rules in isolation (they're pure functions)
- Test scoring dimensions via `ScoringEngine`

## Common Gotchas

- After any code change, reinstall: `pip install -e .`
- CLI stubs return example data — real providers need credentials
- DropCatch auth tokens stored at `~/.config/domains-terminal/`
- DB at `~/.domains-terminal/domains.db` — delete to reset
- `__pycache__` dirs are gitignored
- `dt` is the short alias for `domains-terminal`
