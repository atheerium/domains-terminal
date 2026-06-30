"""ExpiredDomains.net scraper provider.

Purpose: Scrape expiring and recently expired domain lists from
ExpiredDomains.net using requests + BeautifulSoup. Supports optional
authenticated access for restricted sections.

Input: URL, HTML from www.expireddomains.net; optional credentials
Output: List[Domain] persisted to storage
Dependencies: requests, bs4 (BeautifulSoup),
              domains_terminal.models.Domain,
              domains_terminal.storage.Storage
Side effects: HTTP requests to expireddomains.net"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from domains_terminal.models import Domain
from domains_terminal.storage import Storage

logger = logging.getLogger(__name__)

BASE_URL = "https://www.expireddomains.net"
LOGIN_URL = f"{BASE_URL}/login/"
EXPIRING_URL = f"{BASE_URL}/expired-domains/"
EXPIRED_URL = f"{BASE_URL}/deleted-domains/"

# Default request headers to look like a real browser
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ExpiredDomainsError(Exception):
    """Base exception for ExpiredDomains provider errors."""


class LoginError(ExpiredDomainsError):
    """Raised when authentication with ExpiredDomains.net fails."""


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class ExpiredDomainsProvider:
    """Scraper for ExpiredDomains.net domain lists.

    Capable of fetching expiring domains (``get_expiring``) and recently
    deleted/expired domains (``get_expired``). Optionally authenticates to
    access member-only features.

    Usage::

        provider = ExpiredDomainsProvider()
        domains = provider.get_expiring(tld="com", days=7)
    """

    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        storage: Optional[Storage] = None,
    ):
        self.username = username or os.environ.get("EXPIREDDOMAINS_USERNAME") or ""
        self.password = password or os.environ.get("EXPIREDDOMAINS_PASSWORD") or ""
        self.storage = storage or Storage()
        self._session: Optional[requests.Session] = None
        self._logged_in: bool = False

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    @property
    def session(self) -> requests.Session:
        """Get or create a requests Session with default headers."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update(_DEFAULT_HEADERS)
        return self._session

    def login(self) -> None:
        """Log in to ExpiredDomains.net.

        Requires ``username`` and ``password`` to be set (via constructor or
        ``EXPIREDDOMAINS_USERNAME`` / ``EXPIREDDOMAINS_PASSWORD`` env vars).

        Raises ``LoginError`` if credentials are missing or invalid.
        """
        if self._logged_in:
            return

        if not self.username or not self.password:
            raise LoginError(
                "ExpiredDomains.net credentials required. Set username/password "
                "or EXPIREDDOMAINS_USERNAME / EXPIREDDOMAINS_PASSWORD env vars."
            )

        logger.info("Logging in to ExpiredDomains.net as %s ...", self.username)

        # Fetch the login page to obtain CSRF token
        resp = self._get(LOGIN_URL)
        soup = BeautifulSoup(resp.text, "lxml")

        csrf_input = soup.find("input", {"name": "csrf_token"})
        csrf_token = ""
        if csrf_input:
            csrf_token = csrf_input.get("value", "")

        if not csrf_token:
            # Some versions use a different field name
            csrf_input = soup.find("input", {"name": "csrfmiddlewaretoken"})
            if csrf_input:
                csrf_token = csrf_input.get("value", "")

        if not csrf_token:
            logger.warning("Could not find CSRF token; login may fail.")

        login_data: Dict[str, str] = {
            "username": self.username,
            "password": self.password,
        }
        if csrf_token:
            login_data["csrf_token"] = csrf_token

        resp = self.session.post(
            LOGIN_URL,
            data=login_data,
            allow_redirects=True,
            timeout=30,
        )

        # Check for login success (page should no longer have login form)
        if resp.status_code != 200:
            raise LoginError(f"Login returned HTTP {resp.status_code}")

        check_soup = BeautifulSoup(resp.text, "lxml")
        if check_soup.find("input", {"name": "username"}) or "login" in resp.url.lower():
            raise LoginError("Login failed — check your credentials.")

        self._logged_in = True
        logger.info("Successfully logged in to ExpiredDomains.net.")

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_expiring(
        self,
        tld: str = "",
        days: int = 7,
        page: int = 1,
        persist: bool = True,
    ) -> List[Domain]:
        """Scrape expiring domain names from ExpiredDomains.net.

        Args:
            tld: Filter by TLD (e.g. ``"com"``, ``"io"``). Empty string for all.
            days: Number of days until expiry (default 7).
            page: Page number for paginated results.
            persist: If True, persist results to the Storage backend.

        Returns:
            List of ``Domain`` models parsed from the listing.
        """
        params: Dict[str, Any] = {}
        if tld:
            params["tld"] = tld
        if days:
            params["days"] = days
        if page > 1:
            params["page"] = page

        url = f"{EXPIRING_URL}?{urlencode(params)}"
        logger.info(
            "Fetching expiring domains (tld=%s, days=%d, page=%d)",
            tld, days, page,
        )

        resp = self._get(url)
        domains = self._parse_listing(resp.text, source="expireddomains:expiring")

        if persist:
            self._persist_domains(domains)

        logger.info("Retrieved %d expiring domains", len(domains))
        return domains

    def get_expired(
        self,
        days: int = 30,
        page: int = 1,
        persist: bool = True,
    ) -> List[Domain]:
        """Scrape recently deleted / expired domain names.

        This typically requires an authenticated session.

        Args:
            days: Look-back window in days (default 30).
            page: Page number for paginated results.
            persist: If True, persist results to the Storage backend.

        Returns:
            List of ``Domain`` models parsed from the listing.
        """
        params: Dict[str, Any] = {"days": days}
        if page > 1:
            params["page"] = page

        url = f"{EXPIRED_URL}?{urlencode(params)}"
        logger.info("Fetching expired domains (days=%d, page=%d)", days, page)

        resp = self._get(url)
        domains = self._parse_listing(resp.text, source="expireddomains:expired")

        if persist:
            self._persist_domains(domains)

        logger.info("Retrieved %d expired domains", len(domains))
        return domains

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_listing(html: str, source: str = "") -> List[Domain]:
        """Parse the domain table from an ExpiredDomains.net HTML page.

        The site typically uses a ``<table>`` with domain names in a column
        (often the second column, with TLD in a separate column).
        """
        soup = BeautifulSoup(html, "lxml")
        domains: List[Domain] = []

        # Try multiple known table structures
        table = (
            soup.find("table", {"class": "base1"})
            or soup.find("table", {"id": "domains"})
            or soup.find("table", {"class": "tablesorter"})
            or soup.find("table", {"class": "list"})
        )

        if not table:
            # Fallback: try to find any table with domain-like links
            logger.debug("No domain table found, trying link-based fallback.")
            return ExpiredDomainsProvider._parse_domain_links(soup, source)

        rows = table.find_all("tr")
        for row in rows[1:]:  # Skip header
            cols = row.find_all("td")
            if len(cols) < 2:
                continue

            domain_name = ""
            tld_str = ""

            # Domain name is typically a link in the second column
            domain_link = cols[1].find("a") if len(cols) > 1 else None
            if domain_link:
                domain_name = domain_link.get_text(strip=True)
            else:
                domain_name = cols[1].get_text(strip=True) if len(cols) > 1 else ""

            if not domain_name:
                continue

            # Clean domain: remove www., trailing dots, etc.
            domain_name = domain_name.lower().strip().rstrip(".")

            # TLD might be in a separate column (often the third)
            if len(cols) > 2:
                tld_str = cols[2].get_text(strip=True).lower().lstrip(".")
            if not tld_str:
                tld_str = _extract_tld(domain_name)

            # Extract additional data if present
            price = None
            price_text = cols[5].get_text(strip=True) if len(cols) > 5 else ""
            if price_text:
                price = _parse_price(price_text)

            domains.append(Domain(
                domain=domain_name,
                source=source,
                tld=tld_str,
                length=len(domain_name),
                word_count=len(domain_name.split(".")),
                current_price=price,
                status="active",
                raw_data=str(row),
            ))

        return domains

    @staticmethod
    def _parse_domain_links(soup: BeautifulSoup, source: str = "") -> List[Domain]:
        """Fallback: extract domain names from links on the page."""
        domains: List[Domain] = []
        seen: set = set()

        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Many domain links point to /domain/example.com or similar
            domain_match = re.search(r"/domain/([a-z0-9][a-z0-9.-]+\.[a-z]{2,})", href, re.I)
            if domain_match:
                name = domain_match.group(1).lower().strip().rstrip(".")
                if name not in seen:
                    seen.add(name)
                    domains.append(Domain(
                        domain=name,
                        source=source,
                        tld=_extract_tld(name),
                        length=len(name),
                        word_count=len(name.split(".")),
                        status="active",
                    ))

        return domains

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, url: str) -> requests.Response:
        """Make a GET request, optionally authenticating first."""
        try:
            resp = self.session.get(url, timeout=30)
        except requests.RequestException as exc:
            raise ExpiredDomainsError(f"Request failed: {exc}") from exc

        if resp.status_code == 403:
            # Might need login — try once
            if self.username and self.password:
                try:
                    self.login()
                    resp = self.session.get(url, timeout=30)
                    resp.raise_for_status()
                    return resp
                except (LoginError, requests.RequestException) as exc:
                    raise ExpiredDomainsError(
                        f"Access denied (403) even after login: {exc}"
                    ) from exc
            raise ExpiredDomainsError(
                "Access denied (403). ExpiredDomains.net may require login "
                "for this resource."
            )

        if resp.status_code == 404:
            return resp

        try:
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ExpiredDomainsError(
                f"HTTP {resp.status_code}: {resp.text[:200]}"
            ) from exc

        return resp

    def _persist_domains(self, domains: List[Domain]) -> None:
        """Write Domain objects into the storage backend."""
        self.storage.init()
        for d in domains:
            self.storage.insert_domain(d.model_dump())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_tld(domain: str) -> str:
    parts = domain.split(".")
    return parts[-1].lower() if len(parts) > 1 else ""


def _parse_price(text: str) -> Optional[float]:
    """Extract a numeric price from text like ``"$12.50"`` or ``"12,50 €"``."""
    if not text:
        return None
    cleaned = text.replace("$", "").replace("€", "").replace(",", ".").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None
