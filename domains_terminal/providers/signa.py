"""Signa.so trademark provider.

Purpose: Check domain names against trademark databases (USPTO, EUIPO, WIPO)
using the Signa.so API. Provides both single and bulk checking.

Input: Domain names, optional API key (defaults to SIGNA_API_KEY env var),
       optional office filters
Output: Structured dict with conflict results and risk assessment
Dependencies: stdlib (urllib), os
Side effects: HTTPS requests to api.signa.so"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

SIGNA_API = "https://api.signa.so/v1/trademarks"

# Nice classes relevant to domain naming / tech / business
TARGET_CLASSES = [9, 35, 36, 38, 39, 41, 42, 45]
ACTIVE_STATUSES = ["published", "opposition_period", "registered"]


def extract_brand_name(domain: str) -> str:
    """Extract the brand name from a domain.

    Strips protocol, www, TLD, hyphens, and numbers.
    """
    name = domain.lower().strip()
    name = re.sub(r"^https?://", "", name)
    name = re.sub(r"^www\d*\.", "", name)
    parts = name.split(".")
    if len(parts) >= 2:
        name = parts[-2]
    name = re.sub(r"[^a-z]", "", name)
    return name


def _risk_level(conflict: dict[str, Any]) -> str:
    """Determine risk level for a trademark conflict."""
    strategy = conflict.get("strategy", "")
    status = conflict.get("status", {})
    stage = status.get("stage", "")

    if strategy == "exact" and stage == "registered":
        return "high"
    if strategy == "phonetic" and stage == "registered":
        return "medium"
    if stage in ("published", "opposition_period"):
        return "medium"
    return "low"


def search_trademark(api_key: str, query: str, office: str) -> dict[str, Any]:
    """Search Signa API for trademark conflicts."""
    payload = {
        "query": query,
        "strategies": ["exact", "phonetic", "fuzzy", "prefix"],
        "filters": {
            "offices": [office],
            "nice_classes": TARGET_CLASSES,
            "status_stage": ACTIVE_STATUSES,
        },
        "limit": 20,
    }

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        SIGNA_API,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "domains-terminal/0.1.0",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.warning("Signa API error %d: %s", e.code, body[:200])
        return {"data": [], "error": str(e)}
    except URLError as e:
        logger.warning("Signa connection error: %s", e.reason)
        return {"data": [], "error": str(e)}


def check_trademark(
    domain: str,
    api_key: str | None = None,
    offices: list[str] | None = None,
) -> dict[str, Any]:
    """Check trademark availability for a single domain.

    Returns
    -------
    dict
        {domain, name_extracted, office_results: {office: {...}},
         overall_risk: "pass"|"review"|"fail"|"error", conflicts: [...]}
    """
    key = api_key or os.environ.get("SIGNA_API_KEY")
    if not key:
        return {
            "domain": domain,
            "error": "No SIGNA_API_KEY found in environment or parameter",
            "overall_risk": "error",
        }

    office_list = offices or ["uspto", "euipo", "wipo"]
    name = extract_brand_name(domain)

    office_results: dict[str, dict[str, Any]] = {}
    all_conflicts: list[dict[str, Any]] = []

    for office in office_list:
        raw = search_trademark(key, name, office)

        # Detect auth errors
        if "error" in raw:
            return {
                "domain": domain,
                "error": raw.get("error"),
                "overall_risk": "error",
            }

        results = raw.get("data", [])

        for tm in results:
            all_conflicts.append({
                "mark_text": tm.get("mark_text"),
                "strategy": tm.get("strategy"),
                "risk": _risk_level(tm),
                "status_stage": tm.get("status", {}).get("stage"),
                "owner_name": tm.get("owner_name"),
                "nice_classes": [c.get("nice_class") for c in tm.get("classifications", [])],
                "filing_date": tm.get("filing_date"),
                "relevance_score": tm.get("relevance_score"),
                "office": office,
            })

        office_results[office] = {"total": len(results), "conflicts": all_conflicts}

    # Determine overall risk
    has_high = any(c["risk"] == "high" for c in all_conflicts)
    has_medium = any(c["risk"] == "medium" for c in all_conflicts)

    if has_high:
        overall_risk = "fail"
    elif has_medium:
        overall_risk = "review"
    else:
        overall_risk = "pass"

    return {
        "domain": domain,
        "name_extracted": name,
        "office_results": office_results,
        "overall_risk": overall_risk,
        "conflicts": all_conflicts,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def check_trademark_bulk(
    domains: list[str],
    api_key: str | None = None,
    offices: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Check trademark availability for multiple domains.

    Rate-limits with 0.5s delay between requests to avoid API limits.
    """
    results: list[dict[str, Any]] = []
    for domain in domains:
        try:
            r = check_trademark(domain, api_key, offices)
            results.append(r)
            time.sleep(0.5)  # Rate limit
        except Exception as e:
            logger.error("Trademark check failed for %s: %s", domain, e)
            results.append({
                "domain": domain,
                "error": str(e),
                "overall_risk": "error",
            })
    return results