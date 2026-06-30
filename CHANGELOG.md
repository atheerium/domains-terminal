# Changelog

## v0.1.0 (2026-06-29)

### Added
- Initial release: Domains Terminal (formerly domain-agent)
- 9 CLI commands: `init`, `scrape`, `filter`, `score`, `enrich`, `appraise`, `top`, `stats`, `pipeline`
- Pydantic models: Domain, Score, Appraisal, Sale, Event, Metric, PipelineResult
- SQLite storage with schema auto-init
- 3 providers: DropCatch (API v2), ExpiredDomains (scraper), NameBio (API + scrape)
- 12 filter rules: brandable, short, no_numbers, no_hyphens, tld, age, traffic, no_double_letters, vc_ratio, starts_with_letter, ends_with_letter, min_length
- 6 scoring dimensions: brandability, mnemonic, length, tld_value, keywords, pronounceable
- Comparable-sales appraisal engine
- JSON-first output (default) with `--format table` for humans
- `dt` and `domains-terminal` CLI entry points
- AI-friendly documentation: AI_CONTEXT.md, ARCHITECTURE.md, AGENT.md, CONTRIBUTING.md
- Architecture Decision Records (ADRs) in docs/decisions/

### Changed
- Renamed from `domain-agent` to `domains-terminal`
- Config directory: `~/.domain-agent/` → `~/.domains-terminal/`
- DropCatch config directory: `~/.config/dropcatch-cli/` → `~/.config/domains-terminal/`
- CLI alias: `domain-agent` → `dt`

### Removed
- Old `dc` monolithic script
- Old `dropcatch-cli` package
- Old `domain-agent` project directory

### Known Issues
- CLI `scrape`, `filter`, `score`, `enrich`, `appraise`, `pipeline` use stub data (not wired to real engines)
- No tests yet
- No CI pipeline
