"""CLI entry point for Domains Terminal.

Inspired by the Bloomberg Terminal — one command to discover, analyse, and
acquire premium domain names.  Every command outputs JSON by default so
LLM agents can interact with the tool programmatically.

Usage::

    dt init
    dt scrape --source dropcatch --tld com,io
    dt filter --rules brandable,short
    dt score --rules brandability,length
    dt enrich --source namebio
    dt appraise --limit 50
    dt top --limit 10 --min-score 70
    dt stats
    dt pipeline --sources dropcatch --rules brandable,short

All commands output JSON by default.  Pass ``--format table`` for tabular output.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List, Optional

import click

from domains_terminal.models import PipelineResult
from domains_terminal.storage import Storage
from domains_terminal.utils import format_output, pluralize, setup_logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _output(
    data: List[Dict[str, Any]],
    output_format: str,
    *,
    meta: Optional[Dict[str, Any]] = None,
    command: str = "",
    status: str = "ok",
) -> None:
    """Build format string and write to stdout."""
    text = format_output(
        data,
        fmt=output_format,
        meta=meta,
        command=command,
        status=status,
    )
    click.echo(text)


def _get_storage() -> Storage:
    """Return a default Storage instance (lazy)."""
    return Storage()


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version="0.1.0", prog_name="domains-terminal")
def cli() -> None:
    """Domains Terminal — Bloomberg Terminal for domain flipping.

    Scrape, score, appraise, and acquire premium domain names.
    Outputs JSON by default for LLM agent consumption.
    """


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def init(output_format: str) -> None:
    """Create and initialise the SQLite database."""
    setup_logging()
    storage = _get_storage()
    try:
        storage.init()
        db_path = str(storage.db_path)
        _output(
            data=[{"database": db_path, "status": "created"}],
            output_format=output_format,
            command="init",
            meta={"db_path": db_path},
        )
    except Exception as exc:
        logger.exception("Failed to initialise database")
        _output(
            data=[],
            output_format=output_format,
            command="init",
            status="error",
            meta={"error": str(exc)},
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# scrape
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--source",
    default="dropcatch",
    help="Provider to scrape (dropcatch, expireddomains, namebio).",
)
@click.option(
    "--tld",
    default="",
    help="Comma-separated list of TLDs (e.g. 'com,io').",
)
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def scrape(source: str, tld: str, output_format: str) -> None:
    """Scrape domain names from a provider."""
    setup_logging()
    tlds = [t.strip() for t in tld.split(",") if t.strip()] if tld else []

    # --- stub: simulate a scrape result ---
    data: List[Dict[str, Any]] = [
        {
            "domain": "example.io",
            "source": source,
            "tld": "io",
            "length": 10,
            "current_price": None,
        },
        {
            "domain": "startup.ai",
            "source": source,
            "tld": "ai",
            "length": 9,
            "current_price": 199.0,
        },
    ]
    # Filter by TLD when requested
    if tlds:
        data = [d for d in data if d.get("tld", "") in tlds]

    _output(
        data=data,
        output_format=output_format,
        command="scrape",
        meta={
            "source": source,
            "tlds": tlds,
            "count": len(data),
        },
    )


# ---------------------------------------------------------------------------
# filter
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--rules",
    default="brandable",
    help="Comma-separated rule names (e.g. 'brandable,short,no_numbers').",
)
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def filter(rules: str, output_format: str) -> None:  # noqa: A001
    """Filter domains by named rules."""
    setup_logging()
    rule_list = [r.strip() for r in rules.split(",") if r.strip()]

    # --- stub ---
    data: List[Dict[str, Any]] = [
        {"domain": "brandable.io", "pass": True, "failed_rules": []},
        {"domain": "bad-domain-name-123.com", "pass": False, "failed_rules": ["brandable", "short"]},
    ]

    _output(
        data=data,
        output_format=output_format,
        command="filter",
        meta={
            "rules": rule_list,
            "passed": sum(1 for d in data if d.get("pass")),
            "total": len(data),
        },
    )


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--rules",
    default="brandability,length",
    help="Comma-separated scoring dimensions (e.g. 'brandability,length,tld_value').",
)
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def score(rules: str, output_format: str) -> None:  # noqa: A001
    """Score domains across multiple dimensions."""
    setup_logging()
    rule_list = [r.strip() for r in rules.split(",") if r.strip()]

    # --- stub ---
    data: List[Dict[str, Any]] = [
        {"domain": "example.io", "rule": "brandability", "score": 82, "confidence": 0.85},
        {"domain": "example.io", "rule": "length", "score": 100, "confidence": 1.0},
        {"domain": "startup.ai", "rule": "brandability", "score": 68, "confidence": 0.72},
        {"domain": "startup.ai", "rule": "length", "score": 85, "confidence": 0.9},
    ]
    # Filter to requested rules only
    data = [d for d in data if d.get("rule") in rule_list]

    _output(
        data=data,
        output_format=output_format,
        command="score",
        meta={"rules": rule_list, "count": len(data)},
    )


# ---------------------------------------------------------------------------
# enrich
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--source",
    default="namebio",
    help="Data source for enrichment (namebio, whois, archive).",
)
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def enrich(source: str, output_format: str) -> None:
    """Enrich domains with external data (sales, metrics, WHOIS)."""
    setup_logging()

    # --- stub ---
    data: List[Dict[str, Any]] = [
        {
            "domain": "example.io",
            "source": source,
            "metric_type": "monthly_visits",
            "value": "1200",
        },
        {
            "domain": "example.io",
            "source": source,
            "metric_type": "archive_year",
            "value": "2015",
        },
    ]

    _output(
        data=data,
        output_format=output_format,
        command="enrich",
        meta={"source": source, "count": len(data)},
    )


# ---------------------------------------------------------------------------
# appraise
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--limit",
    default=50,
    type=int,
    help="Maximum number of domains to appraise.",
)
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def appraise(limit: int, output_format: str) -> None:
    """Appraise domains and estimate market value."""
    setup_logging()

    # --- stub ---
    data: List[Dict[str, Any]] = [
        {
            "domain": "example.io",
            "retail_min": 500,
            "retail_max": 1500,
            "wholesale_min": 200,
            "wholesale_max": 600,
            "buy_recommendation": True,
            "confidence": 0.72,
            "reason": "Based on 5 comparable sales (median $800) | confidence 72%",
        },
        {
            "domain": "startup.ai",
            "retail_min": 100,
            "retail_max": 400,
            "wholesale_min": 30,
            "wholesale_max": 120,
            "buy_recommendation": False,
            "confidence": 0.35,
            "reason": "No comparable sales found; using rule-of-thumb | confidence 35%",
        },
    ][:limit]

    _output(
        data=data,
        output_format=output_format,
        command="appraise",
        meta={"limit": limit, "count": len(data)},
    )


# ---------------------------------------------------------------------------
# top
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--limit",
    default=10,
    type=int,
    help="Number of top domains to show.",
)
@click.option(
    "--min-score",
    "min_score",
    default=70,
    type=int,
    help="Minimum score threshold.",
)
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def top(limit: int, min_score: int, output_format: str) -> None:
    """Show top-scoring domains."""
    setup_logging()

    storage = _get_storage()
    try:
        rows = storage.get_top_scores(limit=limit, min_score=min_score)
        _output(
            data=rows,
            output_format=output_format,
            command="top",
            meta={"limit": limit, "min_score": min_score, "count": len(rows)},
        )
    except Exception as exc:
        # Table may not exist yet — show empty result gracefully
        _output(
            data=[],
            output_format=output_format,
            command="top",
            status="ok",
            meta={"limit": limit, "min_score": min_score, "count": 0, "note": str(exc)},
        )


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def stats(output_format: str) -> None:
    """Show database statistics."""
    setup_logging()

    storage = _get_storage()
    try:
        domains = storage.execute("SELECT COUNT(*) as cnt FROM domains")
        scores = storage.execute("SELECT COUNT(*) as cnt FROM scores")
        appraisals = storage.execute("SELECT COUNT(*) as cnt FROM appraisals")
        events = storage.execute("SELECT COUNT(*) as cnt FROM events")

        domain_count = domains[0]["cnt"] if domains else 0
        score_count = scores[0]["cnt"] if scores else 0
        appraisal_count = appraisals[0]["cnt"] if appraisals else 0
        event_count = events[0]["cnt"] if events else 0
    except Exception:
        domain_count = score_count = appraisal_count = event_count = 0

    data: List[Dict[str, Any]] = [
        {"table": "domains", "count": domain_count},
        {"table": "scores", "count": score_count},
        {"table": "appraisals", "count": appraisal_count},
        {"table": "events", "count": event_count},
    ]
    total = domain_count + score_count + appraisal_count + event_count

    _output(
        data=data,
        output_format=output_format,
        command="stats",
        meta={
            "total_records": total,
            "summary": f"{pluralize(domain_count, 'domain')}, "
            f"{pluralize(score_count, 'score')}, "
            f"{pluralize(appraisal_count, 'appraisal')}, "
            f"{pluralize(event_count, 'event')}",
        },
    )


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--sources",
    default="dropcatch",
    help="Comma-separated provider names.",
)
@click.option(
    "--rules",
    default="brandable,short",
    help="Comma-separated rule names.",
)
@click.option(
    "--format",
    "output_format",
    default="json",
    type=click.Choice(["json", "table"], case_sensitive=False),
    help="Output format",
)
def pipeline(sources: str, rules: str, output_format: str) -> None:
    """Run the full pipeline: scrape → filter → score → appraise."""
    setup_logging()
    source_list = [s.strip() for s in sources.split(",") if s.strip()]
    rule_list = [r.strip() for r in rules.split(",") if r.strip()]

    # --- stub ---
    data: List[Dict[str, Any]] = [
        {
            "step": "scrape",
            "status": "ok",
            "count": 150,
            "detail": f"Scraped from {', '.join(source_list)}",
        },
        {
            "step": "filter",
            "status": "ok",
            "count": 23,
            "detail": f"Passed rules: {', '.join(rule_list)}",
        },
        {
            "step": "score",
            "status": "ok",
            "count": 23,
            "detail": "Scored across brandability, length",
        },
        {
            "step": "appraise",
            "status": "ok",
            "count": 5,
            "detail": "Top 5 appraisals with buy recommendations",
        },
    ]

    _output(
        data=data,
        output_format=output_format,
        command="pipeline",
        meta={
            "sources": source_list,
            "rules": rule_list,
            "steps": len(data),
        },
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the ``domains-terminal`` / ``dt`` console script."""
    cli(auto_envvar_prefix="DT")


if __name__ == "__main__":
    main()
