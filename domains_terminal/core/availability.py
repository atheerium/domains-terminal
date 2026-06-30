"""Domain availability checker — DNS + WHOIS.

Purpose: Check if domain names are registered using fast DNS lookups
or thorough WHOIS queries. Provides bulk processing for both methods.

Input: Domain names (strings)
Output: List of dicts with availability, method, and additional metadata
Dependencies: stdlib, dnspython, python-whois
Side effects: DNS queries to public resolvers, WHOIS queries to IANA servers"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Any

import dns.exception
import dns.resolver
import whois

logger = logging.getLogger(__name__)


def check_simple(domain: str) -> dict[str, Any]:
    """Fast availability check via DNS lookup.

    Uses DNS A/AAAA/NS record queries. If NXDOMAIN or timeout → available.
    If any records found → registered (unavailable).
    """
    # Fast-path: empty or whitespace domains are treated as available (no such thing)
    if not domain or not domain.strip():
        return {
            "domain": domain,
            "available": True,
            "method": "dns",
            "records": [],
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "note": "Empty domain treated as available",
        }

    resolver = dns.resolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 5

    checked_at = datetime.now(timezone.utc).isoformat()
    records = []
    available = False

    try:
        for rtype in ("A", "AAAA", "NS"):
            try:
                answers = resolver.resolve(domain, rtype, raise_on_no_answer=False)
                for rdata in answers:
                    records.append(f"{rtype}:{rdata.to_text()}")
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
                pass
    except Exception as e:
        logger.warning("DNS check failed for %s: %s", domain, e)
        records = []

    if not records:
        available = True

    return {
        "domain": domain,
        "available": available,
        "method": "dns",
        "records": records,
        "checked_at": checked_at,
    }


def check_full(domain: str) -> dict[str, Any]:
    """Thorough availability check via WHOIS.

    Uses python-whois to query registry WHOIS data. If no WHOIS data
    or error → assume available. Otherwise extract registrar and dates.

    Returns
    -------
    dict
        {domain, available, method, registrar, creation_date, expiration_date,
         nameservers, raw_text_snippet, checked_at}
    """
    checked_at = datetime.now(timezone.utc).isoformat()

    try:
        w = whois.whois(domain)
        # whois.whois returns empty dict-like object for unregistered domains
        # Check if any useful data exists
        has_data = bool(w.get("registrar") or w.get("creation_date") or w.get("expiration_date"))

        if not has_data:
            return {
                "domain": domain,
                "available": True,
                "method": "whois",
                "registrar": None,
                "creation_date": None,
                "expiration_date": None,
                "nameservers": [],
                "raw_text_snippet": None,
                "checked_at": checked_at,
            }

        # Extract fields - creation_date and expiration_date may be lists
        creation = w.get("creation_date")
        if isinstance(creation, list):
            creation = creation[0] if creation else None
        if isinstance(creation, datetime):
            creation = creation.isoformat()

        expiration = w.get("expiration_date")
        if isinstance(expiration, list):
            expiration = expiration[0] if expiration else None
        if isinstance(expiration, datetime):
            expiration = expiration.isoformat()

        nameservers = w.get("name_servers") or []
        if isinstance(nameservers, list):
            nameservers = [str(ns) for ns in nameservers]
        else:
            nameservers = []

        return {
            "domain": domain,
            "available": False,
            "method": "whois",
            "registrar": w.get("registrar"),
            "creation_date": creation,
            "expiration_date": expiration,
            "nameservers": nameservers,
            "raw_text_snippet": None,  # whois lib doesn't expose raw text
            "checked_at": checked_at,
        }
    except Exception as e:
        logger.warning("WHOIS check failed for %s: %s", domain, e)
        return {
            "domain": domain,
            "available": True,
            "method": "whois",
            "error": str(e),
            "checked_at": checked_at,
        }


def check_bulk(domains: list[str], method: str = "simple") -> list[dict[str, Any]]:
    """Check availability of multiple domains.

    Parameters
    ----------
    domains:
        List of domain names to check.
    method:
        "simple" for DNS, "full" for WHOIS.

    Returns
    -------
    list[dict]
        One result per input domain, in the same order.
    """
    if method == "full":
        checker = check_full
    else:
        checker = check_simple

    results: list[dict[str, Any]] = []
    for domain in domains:
        try:
            result = checker(domain)
            results.append(result)
        except Exception as e:
            logger.error("Failed checking %s: %s", domain, e)
            results.append({
                "domain": domain,
                "available": False,
                "method": method,
                "error": str(e),
            })
    return results