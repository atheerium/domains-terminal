"""Tests for domain availability checker.

Purpose: Verify DNS and WHOIS availability checks work for registered
and unregistered domains.

Run with: pytest tests/test_availability.py -v"""

from __future__ import annotations

import pytest

import os
import pytest
from domains_terminal.core.availability import check_simple, check_full, check_bulk

skip_network = pytest.mark.skipif(
    os.getenv("NO_NETWORK") == "1",
    reason="Network unavailable – set NO_NETWORK=0 to enable",
)


@skip_network
class TestCheckSimple:
    def test_registered_domain_not_available(self):
        """google.com is registered, should not be available."""
        result = check_simple("google.com")
        assert result["available"] is False
        assert result["method"] == "dns"
        assert "records" in result

    def test_likely_available_domain(self):
        """A nonsense .com should be available (unlikely to be registered)."""
        result = check_simple("xyqwrpzfhjkabc.com")
        assert result["available"] is True
        assert result["method"] == "dns"

    def test_invalid_domain_handled(self):
        """Invalid domains should not crash and return a result."""
        result = check_simple("")
        assert result["available"] is True
        assert result["method"] == "dns"


class TestCheckFull:
    def test_registered_domain_has_registrar(self):
        """google.com WHOIS should have registrar info."""
        result = check_full("google.com")
        assert result["available"] is False
        assert result["method"] == "whois"
        assert result.get("registrar") is not None

    def test_likely_available_domain(self):
        """Nonsense domain should be marked available via WHOIS."""
        result = check_full("xyqwrpzfhjkabc.com")
        assert result["available"] is True

    def test_invalid_domain_handled(self):
        """Invalid domains should not crash."""
        result = check_full("")
        assert result["available"] is True


class TestCheckBulk:
    def test_mixed_domains(self):
        """check_bulk should return results for each input domain."""
        domains = ["google.com", "xyqwrpzfhjkabc.com", "example.com"]
        results = check_bulk(domains, method="simple")
        assert len(results) == 3
        assert all("domain" in r for r in results)
        assert all("available" in r for r in results)

    def test_bulk_simple_vs_full(self):
        """check_bulk with method='full' calls whois for each."""
        domains = ["example.com", "google.com"]
        results = check_bulk(domains, method="full")
        assert len(results) == 2
        assert all(r["method"] == "whois" for r in results)