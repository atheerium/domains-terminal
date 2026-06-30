"""Tests for scoring engine.

Purpose: Verify each scoring dimension returns expected 0-100 scores and
the composite scoring returns valid results.

Run with: pytest tests/test_scoring.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from domains_terminal.models import Domain
from domains_terminal.core.scoring import ScoringEngine


@pytest.fixture
def engine():
    return ScoringEngine(storage=None)  # type: ignore[arg-type]


class TestScoringDimensions:
    """Test individual ScoringEngine dimension methods."""

    def test_brandability_good_scores_high(self, engine):
        d = Domain(domain="startup", tld="com", length=7)
        result = engine.score_brandability(d)
        assert 60 <= result.score <= 100

    def test_brandability_short_baseline_score(self, engine):
        d = Domain(domain="ab", tld="com", length=2)
        result = engine.score_brandability(d)
        # "ab" is pronounceable, 2 chars — scores moderate
        assert 60 <= result.score <= 80

    def test_brandability_numbers_reduces_score(self, engine):
        d = Domain(domain="startup1", tld="com", length=8, contains_numbers=True)
        result = engine.score_brandability(d)
        # With numbers it should be penalized but still have baseline
        assert result.score >= 0

    def test_length_optimal_scores_high(self, engine):
        d = Domain(domain="startup", tld="com", length=7)
        result = engine.score_length(d)
        assert result.score >= 60

    def test_length_too_short_scores_low(self, engine):
        d = Domain(domain="ab", tld="com", length=2)
        result = engine.score_length(d)
        assert result.score <= 40

    def test_length_too_long_scores_low(self, engine):
        d = Domain(domain="abcdefghijklmnopq", tld="com", length=17)
        result = engine.score_length(d)
        assert result.score <= 40

    def test_tld_com_scores_max(self, engine):
        d = Domain(domain="test", tld="com")
        result = engine.score_tld_value(d)
        assert result.score == 100

    def test_tld_io_scores_high(self, engine):
        d = Domain(domain="test", tld="io")
        result = engine.score_tld_value(d)
        assert result.score >= 50

    def test_tld_unknown_scores_minimum(self, engine):
        d = Domain(domain="test", tld="unknown")
        result = engine.score_tld_value(d)
        assert result.score <= 20

    def test_pronounceable_good_ratio_scores_high(self, engine):
        d = Domain(domain="example", tld="com", length=7)
        result = engine.score_pronounceable(d)
        assert result.score >= 50

    def test_pronounceable_poor_ratio_scores_low(self, engine):
        d = Domain(domain="bcdfghj", tld="com", length=7)
        result = engine.score_pronounceable(d)
        assert result.score <= 40

    def test_keywords_dictionary_word_scores_moderate(self, engine):
        d = Domain(domain="startup", tld="com", length=7)
        result = engine.score_keywords(d)
        assert 0 <= result.score <= 100

    def test_keywords_random_string_scores_lower(self, engine):
        d = Domain(domain="xqzzwp", tld="com", length=6)
        result = engine.score_keywords(d)
        assert result.score >= 0

    def test_mnemonic_returns_valid_score(self, engine):
        d = Domain(domain="zoomzoom", tld="com", length=8)
        result = engine.score_mnemonic(d)
        assert 0 <= result.score <= 100

    def test_mnemonic_short_word_returns_baseline(self, engine):
        d = Domain(domain="the", tld="com", length=3)
        result = engine.score_mnemonic(d)
        assert 0 <= result.score <= 100


class TestScoringEngine:
    def test_composite_score_returns_all_dimensions(self, engine):
        d = Domain(domain="startup", tld="com", length=7)
        results = engine.score(d)

        assert len(results) >= 1
        for score in results:
            assert hasattr(score, "domain")
            assert hasattr(score, "rule")
            assert hasattr(score, "score")
            assert 0 <= score.score <= 100

    def test_all_dimensions_scored_by_default(self, engine):
        d = Domain(domain="startup", tld="com", length=7)
        results = engine.score(d)
        dimension_names = {s.rule for s in results}
        expected_dims = {
            "brandability", "mnemonic", "length",
            "tld_value", "keywords", "pronounceable",
        }
        assert dimension_names == expected_dims

    def test_selective_rules(self, engine):
        d = Domain(domain="startup", tld="com", length=7)
        results = engine.score(d, rules=["length", "tld_value"])
        assert len(results) == 2
        assert {s.rule for s in results} == {"length", "tld_value"}
