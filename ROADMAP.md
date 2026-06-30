# Roadmap

## Current Sprint (v0.1.x)

- [ ] Wire `dt pipeline` to use real engine (filter.py, scoring.py, appraise.py) instead of stub data
- [ ] Wire `dt scrape` to call real providers when credentials are configured
- [ ] Add `dt auth` command for DropCatch credential configuration
- [ ] Write tests for all 12 filter rules
- [ ] Write tests for all 6 scoring dimensions
- [ ] Write tests for appraisal engine

## Backlog

- **More providers**: GoDaddy Auctions, Sedo, Afternic, NameCheap
- **Bulk download**: Wire `dt scrape --bulk` to DropCatch bulk download API
- **Watch mode**: `dt auctions list --watch 60` — poll and report changes
- **Price filters**: Filter by current_price, reserve price
- **Export**: `dt export --format csv` / `dt export --format jsonl`
- **CLI completions**: Shell completion for zsh/bash/fish
- **CI pipeline**: GitHub Actions with pytest on push
- **Pre-commit hooks**: black, ruff, pytest via pre-commit
- **CLI analytics**: Track command usage and timing
- **Documentation site**: GitHub Pages from docs/

## Completed

- ✅ Project skeleton and package setup
- ✅ Pydantic models (Domain, Score, Appraisal, Sale, Event, Metric, PipelineResult)
- ✅ SQLite storage with full CRUD
- ✅ DropCatch v2 API client with OAuth2
- ✅ ExpiredDomains scraper with BeautifulSoup
- ✅ NameBio sales data client
- ✅ 12 filter rules (brandable, short, no_numbers, ...)
- ✅ 6 scoring dimensions (brandability, mnemonic, length, TLD, keywords, pronounceable)
- ✅ Appraisal engine with comparable sales
- ✅ Click CLI with 9 commands
- ✅ JSON + table output (`--format table`)
- ✅ AI-friendly documentation (AI_CONTEXT.md, AGENT.md, docs/)
- ✅ Renamed from domain-agent to domains-terminal
- ✅ GitHub repo at atheerium/domains-terminal

## Ideas (Not Yet Prioritized)

- Web UI with FastAPI + HTMX
- Domain portfolio tracking (buy/sell/hold)
- Price alerts when domains hit target prices
- Integration with domain registrars (Namecheap, GoDaddy API)
- Batch appraisal reports
- Domain name generation (keyword → domain suggestions)
