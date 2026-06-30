"""NameBio domain sales data provider.

Purpose: Fetch historical domain sales from NameBio's public API and website.
Provides comparable sales data for the appraisal engine. API key optional —
falls back to web scraping.

Input: Search keywords or domain names; API JSON from api.namebio.com
Output: List[Sale] persisted to storage (sales_cache table)
Dependencies: requests, bs4 (BeautifulSoup), domains_terminal.models.Sale
Side effects: HTTP requests to namebio.com"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from domains_terminal.models import Sale

logger = logging.getLogger(__name__)

API_BASE = "https://api.namebio.com"
PUBLIC_URL = "https://namebio.com"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.5",
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class NameBioError(Exception):
    """Base exception for NameBio provider errors."""


class RateLimitError(NameBioError):
    """Raised when the NameBio API rate limit is exceeded."""


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class NameBioProvider:
    """Client for NameBio domain sales data.

    Provides methods to search historical domain sales and fetch comparables
    for a given domain. Uses the NameBio public API with optional API key.

    Usage::

        provider = NameBioProvider()
        sales = provider.search_sales("example", limit=20)
        comps = provider.get_comps("example.com")
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("NAMEBIO_API_KEY") or ""

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def search_sales(
        self,
        keyword: str,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Sale]:
        """Search NameBio for domain sales matching a keyword.

        Args:
            keyword: Search term to match against domain names.
            limit: Maximum number of results (default 10, max 100).
            start_date: Filter sales from this date (``"YYYY-MM-DD"``).
            end_date: Filter sales until this date (``"YYYY-MM-DD"``).

        Returns:
            List of ``Sale`` models from the search results.
        """
        logger.info(
            "Searching NameBio sales (keyword=%s, limit=%d)",
            keyword, limit,
        )

        # Try the API first
        try:
            sales = self._api_search(keyword, limit, start_date, end_date)
            if sales:
                logger.info("Retrieved %d sales from NameBio API", len(sales))
                return sales
        except (NameBioError, requests.RequestException) as exc:
            logger.warning("NameBio API search failed, trying scrape: %s", exc)

        # Fallback to scraping the public website
        sales = self._scrape_search(keyword, limit)
        logger.info("Retrieved %d sales from NameBio scrape", len(sales))
        return sales

    def get_comps(
        self,
        domain: str,
        limit: int = 10,
    ) -> List[Sale]:
        """Get comparable sales for a domain.

        Extracts meaningful keywords from the domain name and searches for
        comparable sales (same TLD, similar length/terms).

        Args:
            domain: The domain name to find comparables for (e.g.
                ``"example.com"``).
            limit: Maximum number of comparable sales to return.

        Returns:
            List of ``Sale`` models for comparable domains.
        """
        logger.info("Getting comparables for %s (limit=%d)", domain, limit)

        # Extract the SLD (main keyword) from the domain
        sld = _extract_sld(domain)
        tld = _extract_tld(domain)

        # Search for the keyword (with and without TLD filter)
        sales = self.search_sales(sld, limit=limit)

        # Filter to same TLD if we have enough results
        same_tld = [s for s in sales if s.domain and s.domain.endswith(f".{tld}")]
        if len(same_tld) >= min(limit, 3):
            return same_tld[:limit]

        return sales[:limit]

    # ------------------------------------------------------------------
    # API client
    # ------------------------------------------------------------------

    def _api_search(
        self,
        keyword: str,
        limit: int = 10,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Sale]:
        """Query the NameBio public API."""
        payload: Dict[str, Any] = {
            "search_term": keyword,
        }

        # The free API uses a capped limit
        capped_limit = min(limit, 100)
        if capped_limit > 0:
            payload["page"] = 1

        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if self.api_key:
            payload["api_key"] = self.api_key

        headers = {**_DEFAULT_HEADERS, "Content-Type": "application/json"}

        try:
            resp = requests.post(
                API_BASE,
                json=payload,
                headers=headers,
                timeout=30,
            )
        except requests.ConnectionError as exc:
            raise NameBioError(f"Network error: {exc}") from exc
        except requests.Timeout as exc:
            raise NameBioError("NameBio API timed out.") from exc

        if resp.status_code == 429:
            raise RateLimitError("NameBio API rate limit exceeded.")

        if resp.status_code not in (200, 201):
            logger.warning(
                "NameBio API returned HTTP %d: %s",
                resp.status_code, resp.text[:200],
            )
            return []

        try:
            data = resp.json()
        except json.JSONDecodeError:
            logger.warning("NameBio returned invalid JSON: %s", resp.text[:200])
            return []

        records = data.get("records") or []
        return self._parse_api_records(records, keyword)

    # ------------------------------------------------------------------
    # Scrape fallback
    # ------------------------------------------------------------------

    def _scrape_search(self, keyword: str, limit: int = 10) -> List[Sale]:
        """Fallback: scrape NameBio public search results page."""
        url = f"{PUBLIC_URL}/?s={_url_encode(keyword)}"
        headers = {
            "User-Agent": _DEFAULT_HEADERS["User-Agent"],
            "Accept": "text/html, */*",
            "Accept-Language": "en-US,en;q=0.5",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("NameBio scrape failed: %s", exc)
            return []

        return self._parse_scraped_results(resp.text, keyword, limit)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_api_records(records: List[Dict[str, Any]], keyword: str) -> List[Sale]:
        """Map NameBio API records to Sale models."""
        sales: List[Sale] = []
        for rec in records:
            domain_name = rec.get("Domain") or rec.get("domain") or ""
            price_raw = rec.get("Price") or rec.get("price") or 0
            date_raw = rec.get("Date") or rec.get("date") or ""
            venue = rec.get("Venue") or rec.get("venue") or ""

            price = _parse_price(price_raw)

            sales.append(Sale(
                keyword=keyword,
                domain=domain_name.lower() if domain_name else None,
                sale_price=price,
                sale_date=date_raw,
                venue=venue,
            ))
        return sales

    @staticmethod
    def _parse_scraped_results(html: str, keyword: str, limit: int) -> List[Sale]:
        """Parse NameBio HTML search results into Sale models."""
        soup = BeautifulSoup(html, "lxml")
        sales: List[Sale] = []

        # Try common table structures
        table = (
            soup.find("table", {"class": "results"})
            or soup.find("table", {"id": "domain-sales"})
            or soup.find("table", {"class": "tablesorter"})
        )
        if not table:
            # Try pre-formatted result divs
            return NameBioProvider._parse_result_divs(soup, keyword, limit)

        rows = table.find_all("tr")
        for row in rows[1:]:  # Skip header
            if len(sales) >= limit:
                break
            cols = row.find_all("td")
            if len(cols) < 3:
                continue

            domain_tag = cols[0].find("a") or cols[0]
            domain_name = domain_tag.get_text(strip=True)

            price_text = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            price = _parse_price(price_text)

            date_text = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            venue_text = cols[3].get_text(strip=True) if len(cols) > 3 else ""

            if not domain_name or price is None:
                continue

            sales.append(Sale(
                keyword=keyword,
                domain=domain_name.lower(),
                sale_price=price,
                sale_date=date_text,
                venue=venue_text,
            ))

        return sales

    @staticmethod
    def _parse_result_divs(soup: BeautifulSoup, keyword: str, limit: int) -> List[Sale]:
        """Fallback: parse NameBio results from ``<div>`` elements."""
        sales: List[Sale] = []
        for div in soup.find_all("div", class_=re.compile(r"result|sale|row", re.I)):
            if len(sales) >= limit:
                break
            domain_el = div.find("span", class_="domain") or div.find("a")
            if not domain_el:
                continue
            domain_name = domain_el.get_text(strip=True)
            if not domain_name:
                continue

            price_el = div.find("span", class_=re.compile(r"price", re.I))
            price_text = price_el.get_text(strip=True) if price_el else ""
            price = _parse_price(price_text)

            date_el = div.find("span", class_=re.compile(r"date", re.I))
            date_text = date_el.get_text(strip=True) if date_el else ""

            venue_el = div.find("span", class_=re.compile(r"venue", re.I))
            venue_text = venue_el.get_text(strip=True) if venue_el else ""

            if price is None:
                continue

            sales.append(Sale(
                keyword=keyword,
                domain=domain_name.lower(),
                sale_price=price,
                sale_date=date_text,
                venue=venue_text,
            ))

        return sales


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_sld(domain: str) -> str:
    """Return the second-level domain (main name part, no TLD).

    ``"example.com"`` → ``"example"``
    ``"www.example.co.uk"`` → ``"example"``
    """
    cleaned = domain.lower().strip().rstrip(".")
    parts = cleaned.split(".")
    # Skip common subdomains like www, mail
    if parts[0] in ("www", "mail", "ftp", "smtp") and len(parts) > 2:
        return parts[1]
    return parts[0]


def _extract_tld(domain: str) -> str:
    parts = domain.lower().strip().rstrip(".").split(".")
    return parts[-1] if len(parts) > 1 else ""


def _parse_price(val: Any) -> int:
    """Convert a price value to integer cents/whole dollars.

    Handles ``"$1,234"``, ``1234``, ``"1234.56"``, etc.
    """
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    cleaned = str(val).replace("$", "").replace(",", "").replace("€", "").strip()
    try:
        # Round to nearest integer dollar
        return int(round(float(cleaned)))
    except (ValueError, TypeError):
        return 0


def _url_encode(s: str) -> str:
    """Minimal URL encoding for a search term."""
    return s.replace(" ", "+").replace("&", "%26")
