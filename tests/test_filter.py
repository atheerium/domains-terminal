"""Tests for filter predicates and engine.

Purpose: Verify each filter rule behaves correctly in isolation and the
Filter class composes rules properly.

Run with: pytest tests/test_filter.py -v
"""

from __future__ import annotations

import pytest

from domains_terminal.core.filter import (
    rule_brandable,
    rule_short,
    rule_no_numbers,
    rule_no_hyphens,
    rule_tld,
    rule_no_double_letters,
    rule_vowel_consonant_ratio,
    rule_starts_with_letter,
    rule_ends_with_letter,
    rule_min_length,
    known_rules,
)
from domains_terminal.models import Domain


class TestRuleBrandable:
    def test_brandable_domain_passes(self, domain_sample):
        """example (7 chars, no numbers/hyphens, pronounceable) should pass."""
        name = domain_sample.domain  # "example"
        d = Domain(domain=name, tld="com", length=len(name))
        assert rule_brandable(d) is True

    def test_too_short_fails(self):
        """Domains under 6 chars are not brandable."""
        d = Domain(domain="ab", tld="com", length=2)
        assert rule_brandable(d) is False

    def test_too_long_fails(self):
        """Domains over 12 chars are not brandable."""
        d = Domain(domain="abcdefghijklmno", tld="com", length=15)
        assert rule_brandable(d) is False

    def test_numbers_fail(self, domain_with_numbers):
        """Domains containing digits are not brandable."""
        assert rule_brandable(domain_with_numbers) is False

    def test_hyphens_fail(self, domain_with_hyphen):
        """Domains containing hyphens are not brandable."""
        assert rule_brandable(domain_with_hyphen) is False

    def test_unpronounceable_fails(self):
        """Domains with extreme vowel ratio (<0.25) should fail."""
        d = Domain(domain="bcdfghj", tld="com", length=7)
        assert rule_brandable(d) is False


class TestRuleShort:
    def test_short_domain_passes(self, domain_short):
        """go (2 chars) should pass default max_length=8."""
        assert rule_short(domain_short) is True

    def test_custom_max_length(self, domain_sample):
        """example (7 chars) passes with max_length=10."""
        assert rule_short(domain_sample, max_length=10) is True

    def test_long_fails_with_small_max(self, domain_sample):
        """example (7 chars) fails with max_length=4."""
        assert rule_short(domain_sample, max_length=4) is False


class TestRuleNoNumbers:
    def test_no_numbers_passes(self, domain_sample):
        assert rule_no_numbers(domain_sample) is True

    def test_numbers_fail(self, domain_with_numbers):
        assert rule_no_numbers(domain_with_numbers) is False


class TestRuleNoHyphens:
    def test_no_hyphens_passes(self, domain_sample):
        assert rule_no_hyphens(domain_sample) is True

    def test_hyphen_fails(self, domain_with_hyphen):
        assert rule_no_hyphens(domain_with_hyphen) is False


class TestRuleTld:
    def test_allowed_tld_passes(self, domain_sample):
        domain_sample.tld = "com"
        assert rule_tld(domain_sample, allowed=["com"]) is True

    def test_disallowed_tld_fails(self, domain_sample):
        domain_sample.tld = "xyz"
        assert rule_tld(domain_sample, allowed=["com"]) is False

    def test_dot_prefix_normalized(self, domain_sample):
        domain_sample.tld = "io"
        assert rule_tld(domain_sample, allowed=[".io"]) is True


class TestRuleNoDoubleLetters:
    def test_no_double_passes(self):
        d = Domain(domain="example", tld="com", length=7)
        assert rule_no_double_letters(d) is True

    def test_double_letter_fails(self):
        d = Domain(domain="exxample", tld="com", length=8)
        assert rule_no_double_letters(d) is False

    def test_empty_fails(self):
        d = Domain(domain="", tld="com", length=0)
        assert rule_no_double_letters(d) is False


class TestRuleVowelConsonantRatio:
    def test_balanced_ratio_passes(self):
        d = Domain(domain="example", tld="com", length=7)
        assert rule_vowel_consonant_ratio(d) is True

    def test_extreme_ratio_fails(self):
        d = Domain(domain="bcdfgh", tld="com", length=6)
        assert rule_vowel_consonant_ratio(d) is False

    def test_custom_range(self):
        d = Domain(domain="aeiou", tld="com", length=5)
        assert rule_vowel_consonant_ratio(d, min_ratio=0.8, max_ratio=1.0) is True


class TestRuleStartsEndsWithLetter:
    def test_starts_with_letter_passes(self, domain_sample):
        assert rule_starts_with_letter(domain_sample) is True

    def test_starts_with_digit_fails(self, domain_with_numbers):
        # "12go123" starts with '1' (a digit) but still a number
        assert rule_starts_with_letter(domain_with_numbers) is False

    def test_ends_with_letter_passes(self, domain_sample):
        assert rule_ends_with_letter(domain_sample) is True

    def test_ends_with_digit_fails(self, domain_with_numbers):
        assert rule_ends_with_letter(domain_with_numbers) is False


class TestRuleMinLength:
    def test_meets_minimum(self, domain_sample):
        assert rule_min_length(domain_sample, min_length=3) is True

    def test_below_minimum(self, domain_short):
        assert rule_min_length(domain_short, min_length=3) is False


class TestKnownRules:
    def test_all_rules_registered(self):
        rules = known_rules()
        expected = {
            "brandable", "short", "no_numbers", "no_hyphens",
            "tld", "age", "traffic", "no_double_letters",
            "vc_ratio", "starts_with_letter", "ends_with_letter",
            "min_length",
        }
        assert set(rules) == expected
