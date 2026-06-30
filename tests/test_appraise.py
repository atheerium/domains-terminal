"""Tests for domain appraisal engine.

Purpose: Verify appraisal engine produces correct value ranges, buy
recommendations, and handles edge cases (no comps, insufficient data).

Run with: pytest tests/test_appraise.py -v
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from domains_terminal.models import Domain, Sale, Score
from domains_terminal.storage import Storage
from domains_terminal.core.appraise import AppraisalEngine


@pytest.fixture
def storage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    s = Storage(db_path=db_path)
    s.init()
    yield s
    db_path.unlink(missing_ok=True)


@pytest.fixture
def engine(storage):
    return AppraisalEngine(storage=storage)


@pytest.fixture
def domain_sample():
    return Domain(
        domain="startup",
        source="dropcatch",
        tld="com",
        length=7,
        word_count=1,
        contains_numbers=False,
        current_price=12.0,
    )


class TestAppraisalEngine:
    def test_appraise_with_comps(self, engine, storage, domain_sample):
        """With manually seeded comps + scores, should produce rational values."""
        # Seed scores into storage
        for score_data in [
            {"domain": "startup", "rule": "brandability", "score": 85, "confidence": 0.9},
            {"domain": "startup", "rule": "length", "score": 75, "confidence": 0.8},
            {"domain": "startup", "rule": "tld_value", "score": 100, "confidence": 0.95},
        ]:
            storage.insert_score(score_data)

        # Seed comps into storage
        for sale_data in [
            {"keyword": "startup", "domain": "startup1.com", "sale_price": 5000, "venue": "namebio"},
            {"keyword": "startup", "domain": "startup2.com", "sale_price": 3000, "venue": "namebio"},
            {"keyword": "startup", "domain": "startup3.io", "sale_price": 2000, "venue": "namebio"},
            {"keyword": "startup", "domain": "startup4.co", "sale_price": 1000, "venue": "sedo"},
            {"keyword": "startup", "domain": "getstartup.com", "sale_price": 4000, "venue": "namebio"},
        ]:
            storage.execute(
                "INSERT INTO sales_cache (keyword, domain, sale_price, venue) VALUES (?, ?, ?, ?)",
                (sale_data["keyword"], sale_data["domain"], sale_data["sale_price"], sale_data["venue"]),
            )

        result = engine.appraise(domain=domain_sample)

        assert result.domain == "startup"
        assert 0 < result.retail_min <= result.retail_max
        assert 0 < result.wholesale_min <= result.wholesale_max
        assert 0.0 <= result.confidence <= 1.0
        assert result.buy_recommendation in (0, 1)
        assert isinstance(result.reason, str) and len(result.reason) > 0

    def test_appraise_without_comps(self, engine, domain_sample):
        """Without comps in storage, should produce fallback heuristic values."""
        result = engine.appraise(domain=domain_sample)

        assert result.domain == "startup"
        assert result.retail_min <= result.retail_max
        assert result.wholesale_min <= result.wholesale_max
        # Without comps, confidence should be low (≤ 0.5)
        assert result.confidence <= 0.5
        assert isinstance(result.reason, str) and len(result.reason) > 0

    def test_appraise_none_domain_raises(self, engine):
        """Appraising None domain should raise."""
        with pytest.raises((ValueError, AttributeError, TypeError)):
            engine.appraise(domain=None)  # type: ignore[arg-type]

    def test_score_influence_on_value(self, engine, storage, domain_sample):
        """Higher scores should produce higher or equal appraisals."""
        # Low scores
        engine.appraise(domain=domain_sample)
        # Without any scores, fallback is used. Now add scores:
        storage.insert_score({"domain": "startup", "rule": "brandability", "score": 30, "confidence": 0.5})

        result_low = engine.appraise(domain=domain_sample)

        # Now add high scores
        storage.insert_score({"domain": "startup", "rule": "brandability", "score": 95, "confidence": 0.9})
        result_high = engine.appraise(domain=domain_sample)

        # Higher composite scores should not produce lower values
        assert result_high.retail_min >= result_low.retail_min or result_high.retail_max >= result_low.retail_max
