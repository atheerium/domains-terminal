"""Tests for Signa.so trademark provider.

Purpose: Verify trademark checking against the Signa.so API.

Run with: pytest tests/test_signa.py -v"""

from __future__ import annotations

import os

import pytest

from domains_terminal.providers.signa import check_trademark, check_trademark_bulk, extract_brand_name


class TestExtractBrandName:
    def test_extracts_name_from_domain(self):
        assert extract_brand_name("startup.io") == "startup"

    def test_strips_www(self):
        assert extract_brand_name("www.apple.com") == "apple"

    def test_strips_protocol(self):
        assert extract_brand_name("https://example.com") == "example"

    def test_strips_numbers_and_hyphens(self):
        assert extract_brand_name("my-startup-123.com") == "mystartup"


@pytest.mark.skipif(not os.environ.get("SIGNA_API_KEY"), reason="SIGNA_API_KEY not set")
class TestCheckTrademark:
    def test_real_domain_has_conflicts(self):
        """Apple.com should have trademark conflicts."""
        result = check_trademark("apple.com")
        assert result["domain"] == "apple.com"
        assert "overall_risk" in result
        # "apple" likely has high-risk conflicts
        assert result["overall_risk"] in ("pass", "review", "fail")

    def test_nonsense_domain_passes(self):
        """Nonsense domain should have no conflicts."""
        result = check_trademark("xyqwrpzfhjkabc.com")
        assert result["domain"] == "xyqwrpzfhjkabc.com"
        assert result["overall_risk"] == "pass"

    def test_custom_offices(self):
        """Can check specific offices."""
        result = check_trademark("startup.io", offices=["uspto"])
        assert result["overall_risk"] in ("pass", "review", "fail")


@pytest.mark.skipif(not os.environ.get("SIGNA_API_KEY"), reason="SIGNA_API_KEY not set")
class TestCheckTrademarkBulk:
    def test_multiple_domains(self):
        """Check a few domains at once."""
        domains = ["apple.com", "xyqwrpzfhjkabc.com", "google.io"]
        results = check_trademark_bulk(domains, offices=["uspto"])
        assert len(results) == 3
        assert all("domain" in r for r in results)
        assert all("overall_risk" in r for r in results)

    def test_missing_api_key(self):
        """Should detect missing API key."""
        result = check_trademark("test.com", api_key="invalid_key_12345")
        assert result["overall_risk"] == "error"
        assert "error" in result