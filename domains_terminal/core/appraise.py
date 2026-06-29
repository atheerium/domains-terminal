"""Domain appraisal engine.

Estimates retail and wholesale values for domains by comparing against
comparable sales (comps) stored in the sales cache.  Produces an ``Appraisal``
object with value ranges, confidence, and a buy recommendation.
"""

from __future__ import annotations

import logging
import re
import statistics
from typing import Any, Dict, List, Optional, Tuple

from domains_terminal.models import Appraisal, Domain, Sale, Score
from domains_terminal.storage import Storage

logger = logging.getLogger(__name__)

# Default multipliers applied to the median comparable price
RETAIL_MULTIPLIER: float = 1.3
WHOLESALE_MULTIPLIER: float = 0.6

# Minimum number of comps required for a comp-based estimate
MIN_COMPS_FOR_ESTIMATE: int = 3

# Base value for domains when comps are insufficient (in USD)
FALLBACK_RETAIL_MIN: int = 50
FALLBACK_RETAIL_MAX: int = 500
FALLBACK_WHOLESALE_MIN: int = 10
FALLBACK_WHOLESALE_MAX: int = 100

# Scoring weights used when incorporating scores into the appraisal
SCORE_CONTRIBUTION: float = 0.20  # 20 % of final estimate can come from scores


class AppraisalEngine:
    """Domain appraisal engine.

    Uses comparable sales data from the ``sales_cache`` table and optional
    ``Score`` records to produce a fair-market estimation.
    """

    def __init__(self, storage: Storage):
        self.storage = storage

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def appraise(self, domain: Domain) -> Appraisal:
        """Produce a full appraisal for *domain*.

        The appraisal combines comparable-sales analysis with any previously
        stored ``Score`` records to determine estimated value ranges and a
        buy recommendation.

        Returns
        -------
        Appraisal
            Populated with retail/wholesale estimates and recommendation.
        """
        logger.info("Appraising %s", domain.domain)

        comps = self.get_comps(domain)
        scores = self._load_scores(domain)

        # Core estimates from comps
        if len(comps) >= MIN_COMPS_FOR_ESTIMATE:
            retail_min = self.estimate_retail(domain, comps)
            retail_max = self._estimate_retail_high(domain, comps)
            wholesale_min = self.estimate_wholesale(domain, comps)
            wholesale_max = self._estimate_wholesale_high(domain, comps)
            confidence = self._compute_confidence(comps, scores)
        else:
            # Fallback to rule-of-thumb when comps are sparse
            retail_min, retail_max, wholesale_min, wholesale_max = self._fallback(domain, scores)
            confidence = 0.15 + len(comps) * 0.05  # low confidence with few comps
            confidence = min(confidence, 0.5)

        # Adjust for current_price and scores
        retail_min, retail_max = self._apply_score_adjustment(domain, scores, retail_min, retail_max)

        # Buy recommendation
        buy_recommendation = self._should_buy(domain, retail_min, wholesale_max, confidence)

        # Build reason string
        reason = self._build_reason(domain, comps, scores, retail_min, wholesale_max, confidence)

        appraisal = Appraisal(
            domain=domain.domain,
            retail_min=retail_min,
            retail_max=retail_max,
            wholesale_min=wholesale_min,
            wholesale_max=wholesale_max,
            buy_recommendation=buy_recommendation,
            confidence=round(confidence, 2),
            reason=reason,
        )

        # Persist
        try:
            self.storage.insert_appraisal(appraisal.model_dump(exclude={"id"}))
        except Exception:
            logger.exception("Failed to persist appraisal for %s", domain.domain)

        return appraisal

    def get_comps(self, domain: Domain) -> list[Sale]:
        """Retrieve comparable sales for *domain*.

        Comparability is determined by:
            1. Same TLD
            2. Similar domain-name length (± 3 characters)
            3. Shared keywords (word overlap in domain name)

        Sales are ordered from most- to least-relevant.
        """
        name_part = domain.domain.split(".")[0].lower() if domain.domain else ""
        tld = domain.tld.lower().lstrip(".")
        name_length = len(name_part)

        # Build a set of tokens from the domain name for keyword matching
        tokens = set(re.split(r"[\d-]+", name_part)) if name_part else set()

        try:
            rows = self.storage.execute("SELECT * FROM sales_cache ORDER BY sale_date DESC")
        except Exception:
            logger.warning("Could not query sales_cache — table may be empty")
            return []

        scored: list[tuple[int, Sale]] = []
        for row in rows:
            sale = Sale(**dict(row))
            score = self._comp_relevance(sale, tld, name_length, tokens)
            if score > 0:
                scored.append((score, sale))

        # Sort by relevance descending, then by recency
        scored.sort(key=lambda pair: (-pair[0], pair[1].sale_date or ""))
        return [s for _, s in scored]

    def estimate_retail(self, domain: Domain, comps: list[Sale]) -> int:
        """Estimate the retail (end-user) price from comparable sales.

        Retail is typically median(comp_prices) × RETAIL_MULTIPLIER.
        """
        if not comps:
            return FALLBACK_RETAIL_MIN
        prices = [s.sale_price for s in comps]
        median = statistics.median(prices)
        return max(1, int(median * RETAIL_MULTIPLIER))

    def estimate_wholesale(self, domain: Domain, comps: list[Sale]) -> int:
        """Estimate the wholesale (reseller) price from comparable sales.

        Wholesale is typically median(comp_prices) × WHOLESALE_MULTIPLIER.
        """
        if not comps:
            return FALLBACK_WHOLESALE_MIN
        prices = [s.sale_price for s in comps]
        median = statistics.median(prices)
        return max(1, int(median * WHOLESALE_MULTIPLIER))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _comp_relevance(
        self,
        sale: Sale,
        tld: str,
        name_length: int,
        tokens: set[str],
    ) -> int:
        """Score a single sale's relevance as a comparable (higher = better)."""
        score = 0

        # -- TLD match (most important) --
        sale_domain = (sale.domain or sale.keyword or "").lower()
        sale_tld = sale_domain.split(".")[-1] if "." in sale_domain else ""
        if sale_tld == tld:
            score += 30

        # -- Length similarity --
        sale_name = sale_domain.split(".")[0] if sale_domain else ""
        if sale_name:
            length_diff = abs(len(sale_name) - name_length)
            if length_diff <= 1:
                score += 20
            elif length_diff <= 3:
                score += 10

        # -- Keyword overlap --
        sale_tokens = set(re.split(r"[\d-]+", sale_name)) if sale_name else set()
        overlap = tokens & sale_tokens
        score += len(overlap) * 10

        # -- Exact keyword match bonus --
        sale_keyword = (sale.keyword or "").lower()
        if tokens and any(t in sale_keyword for t in tokens if t):
            score += 15

        return score

    def _load_scores(self, domain: Domain) -> list[Score]:
        """Load persisted Score records for the domain."""
        try:
            rows = self.storage.get_scores(domain.domain)
            return [Score(**r) for r in rows]
        except Exception:
            return []

    def _estimate_retail_high(self, domain: Domain, comps: list[Sale]) -> int:
        """Upper-bound retail estimate using the upper quartile of comps."""
        prices = sorted(s.sale_price for s in comps)
        idx = len(prices) * 3 // 4
        high_val = prices[min(idx, len(prices) - 1)]
        return max(self.estimate_retail(domain, comps), int(high_val * RETAIL_MULTIPLIER))

    def _estimate_wholesale_high(self, domain: Domain, comps: list[Sale]) -> int:
        """Upper-bound wholesale estimate."""
        base = self.estimate_wholesale(domain, comps)
        return max(base, int(base * 1.5))

    def _compute_confidence(self, comps: list[Sale], scores: list[Score]) -> float:
        """Compute a confidence score (0.0-1.0) for the appraisal.

        Factors: number of comps, price consistency, availability of scores.
        """
        n = len(comps)
        if n == 0:
            return 0.1

        # Volume factor: more comps → higher confidence
        vol = min(1.0, n / 15)

        # Consistency factor: lower CV → higher confidence
        prices = [s.sale_price for s in comps]
        if len(prices) >= 2:
            mean = statistics.mean(prices)
            stdev = statistics.stdev(prices) if len(prices) >= 2 else 0
            cv = stdev / mean if mean > 0 else 1.0
            consistency = max(0.0, 1.0 - cv)
        else:
            consistency = 0.5

        # Score factor
        score_factor = 0.3 if scores else 0.1

        return round(0.4 * vol + 0.4 * consistency + 0.2 * score_factor, 2)

    def _fallback(
        self,
        domain: Domain,
        scores: list[Score],
    ) -> Tuple[int, int, int, int]:
        """Fallback estimate when comps are insufficient.

        Uses domain characteristics (TLD, length) to guess a base range.
        """
        tld = domain.tld.lower().lstrip(".")
        name_part = domain.domain.split(".")[0].lower() if domain.domain else ""

        # TLD base
        tld_premium: Dict[str, float] = {
            "com": 3.0, "org": 2.0, "net": 1.5, "io": 1.2, "co": 1.0,
            "ai": 1.0, "app": 0.8, "dev": 0.8,
        }
        multiplier = tld_premium.get(tld, 0.5)

        # Length bonus
        length = len(name_part)
        if 4 <= length <= 8:
            multiplier *= 1.5
        elif 3 <= length <= 10:
            multiplier *= 1.2

        base = int(100 * multiplier)

        # Score boost
        avg_score = self._avg_score(scores)
        if avg_score > 60:
            base = int(base * 1.5)
        elif avg_score > 40:
            base = int(base * 1.2)

        retail_min = max(FALLBACK_RETAIL_MIN, base)
        retail_max = max(retail_min + 200, int(base * 2.5))
        wholesale_min = max(FALLBACK_WHOLESALE_MIN, int(base * 0.3))
        wholesale_max = max(wholesale_min + 50, int(base * 0.8))

        return retail_min, retail_max, wholesale_min, wholesale_max

    def _apply_score_adjustment(
        self,
        domain: Domain,
        scores: list[Score],
        retail_min: int,
        retail_max: int,
    ) -> Tuple[int, int]:
        """Adjust retail estimate upward if the domain has high scores."""
        avg = self._avg_score(scores)
        if avg <= 0:
            return retail_min, retail_max

        # Boost proportional to average score above 50
        boost = max(0, (avg - 50) / 50) * SCORE_CONTRIBUTION
        if boost <= 0:
            return retail_min, retail_max

        adjustment = int(retail_min * boost)
        return retail_min + adjustment, retail_max + adjustment

    @staticmethod
    def _avg_score(scores: list[Score]) -> float:
        """Average score value across all Score records (0 if empty)."""
        if not scores:
            return 0.0
        return statistics.mean(s.score for s in scores)

    def _should_buy(self, domain: Domain, retail_min: int, wholesale_max: int, confidence: float) -> bool:
        """Determine whether this domain is a good buy.

        A buy is recommended when:
            - The domain has a ``current_price`` set
            - The wholesale value exceeds the current price
            - Confidence is reasonable
        """
        price = domain.current_price
        if price is None or price <= 0:
            return False

        # We want wholesale_max >= current_price (at minimum break even)
        if wholesale_max < price:
            return False

        if confidence < 0.2:
            return False

        # Stronger signal: retail_min > current_price * 2
        if retail_min > price * 2:
            return True

        # Moderate signal: wholesale_max > price * 1.2 and confidence > 0.4
        if wholesale_max > price * 1.2 and confidence >= 0.4:
            return True

        return False

    def _build_reason(
        self,
        domain: Domain,
        comps: list[Sale],
        scores: list[Score],
        retail_min: int,
        wholesale_max: int,
        confidence: float,
    ) -> str:
        """Build a human-readable appraisal reason string."""
        parts: list[str] = []

        # Comparable sales summary
        if comps:
            prices = [s.sale_price for s in comps]
            median = int(statistics.median(prices))
            parts.append(f"Based on {len(comps)} comparable sales (median ${median:,})")
        else:
            parts.append("No comparable sales found; using rule-of-thumb")

        # Score summary
        if scores:
            avg = int(self._avg_score(scores))
            parts.append(f"average score {avg}/100")

        # Price context
        price = domain.current_price
        if price and price > 0:
            margin = int((wholesale_max - price) / price * 100)
            parts.append(f"current price ${price:,.0f} (margin {margin}%)")

        # Confidence
        parts.append(f"confidence {confidence:.0%}")

        return " | ".join(parts)
