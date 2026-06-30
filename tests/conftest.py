"""Shared test fixtures for Domains Terminal tests."""

from __future__ import annotations

from typing import List

import pytest

from domains_terminal.models import Domain, Sale, Score


@pytest.fixture
def domain_sample() -> Domain:
    return Domain(
        domain="example",
        source="dropcatch",
        tld="com",
        length=7,
        word_count=1,
        contains_numbers=False,
        seen_at="2026-06-29T12:00:00Z",
        current_price=12.0,
        auction_id="auction123",
    )


@pytest.fixture
def domain_short() -> Domain:
    return Domain(
        domain="go",
        source="expireddomains",
        tld="io",
        length=2,
        word_count=0,
        contains_numbers=False,
        current_price=15.0,
    )


@pytest.fixture
def domain_with_numbers() -> Domain:
    return Domain(
        domain="12go123",
        source="dropcatch",
        tld="com",
        length=8,
        word_count=0,
        contains_numbers=True,
        current_price=8.0,
    )


@pytest.fixture
def domain_with_hyphen() -> Domain:
    return Domain(
        domain="top-level",
        source="expireddomains",
        tld="com",
        length=9,
        word_count=1,
        contains_numbers=False,
        current_price=11.0,
    )


@pytest.fixture
def domain_long() -> Domain:
    return Domain(
        domain="thisiswaytoolongforbrand",
        source="dropcatch",
        tld="com",
        length=21,
        word_count=0,
        contains_numbers=False,
        current_price=9.0,
    )


@pytest.fixture
def domains_mixed(domain_sample, domain_short, domain_with_numbers, domain_with_hyphen, domain_long) -> List[Domain]:
    return [domain_sample, domain_short, domain_with_numbers, domain_with_hyphen, domain_long]
