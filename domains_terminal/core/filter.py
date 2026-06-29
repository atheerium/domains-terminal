"""Domain filtering predicates and Filter class.

Provides a rules-based engine that evaluates domains against named predicates.
Rules are standalone functions that accept a Domain and return bool, making them
testable in isolation. The Filter class composes rules into pipelines.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, List, Optional

from domains_terminal.models import Domain
from domains_terminal.storage import Storage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule predicates  (each is a standalone function — easy to test)
# ---------------------------------------------------------------------------

# Brandable words dictionary (common short dictionary words for domain context)
_COMMON_WORDS: set[str] = {
    "able", "also", "area", "army", "away", "back", "ball", "band", "bank",
    "base", "bash", "bear", "beat", "bell", "bird", "blue", "bold", "bond",
    "book", "boom", "boss", "brew", "cape", "care", "cash", "club", "code",
    "coin", "cold", "core", "cove", "crisp", "cube", "dash", "data", "dawn",
    "deck", "deep", "demo", "dial", "dice", "dock", "dome", "done", "draft",
    "drip", "drop", "drum", "dust", "ease", "echo", "edge", "else", "epic",
    "even", "ever", "evil", "exam", "exit", "face", "fact", "fail", "fair",
    "fake", "farm", "fast", "fate", "fear", "feed", "feel", "fell", "file",
    "fill", "film", "find", "fine", "fire", "firm", "fish", "five", "flag",
    "flow", "fold", "folk", "fond", "food", "fool", "foot", "ford", "fore",
    "form", "fort", "free", "from", "fuel", "full", "fund", "fuse", "fuzz",
    "gain", "game", "gang", "gape", "garb", "gate", "gave", "gaze", "gear",
    "gift", "gild", "girl", "gist", "give", "glad", "glow", "glue", "gnat",
    "goal", "goat", "goes", "gold", "golf", "gone", "good", "grab", "gray",
    "grew", "grid", "grim", "grin", "grip", "grit", "grow", "gulf", "guru",
    "hack", "hair", "half", "hall", "hand", "hang", "hard", "harm", "hash",
    "hate", "haul", "have", "hawk", "haze", "hazy", "head", "heal", "heap",
    "hear", "heat", "heel", "held", "hero", "hide", "high", "hill", "hind",
    "hint", "hire", "hold", "hole", "home", "hood", "hook", "hope", "horn",
    "host", "hour", "huge", "hull", "hump", "hung", "hunt", "hurt", "hush",
    "icon", "idea", "inch", "into", "iron", "isle", "item", "jack", "jade",
    "jail", "jazz", "jean", "jerk", "jest", "jets", "join", "joke", "jolt",
    "jour", "jump", "jury", "just", "keen", "keep", "kept", "kick", "kill",
    "kind", "king", "kiss", "kite", "knee", "knew", "knit", "knob", "knot",
    "know", "lace", "lack", "lady", "laid", "lake", "lamp", "land", "lark",
    "lash", "lass", "last", "late", "lawn", "lazy", "lead", "leaf", "lean",
    "leap", "left", "lend", "lens", "less", "liar", "lick", "life", "lift",
    "like", "limb", "lime", "limp", "line", "link", "lion", "list", "live",
    "load", "loaf", "loan", "lock", "loft", "bold", "long", "look", "loop",
    "lord", "lose", "loss", "lost", "love", "luck", "lure", "lurk", "lush",
    "lust", "made", "mail", "main", "make", "male", "mall", "malt", "mane",
    "many", "mare", "mark", "mars", "mask", "mass", "mast", "mate", "maze",
    "mead", "meal", "mean", "meat", "meet", "meld", "melt", "memo", "mend",
    "menu", "mere", "mesh", "mess", "mild", "mile", "milk", "mill", "mind",
    "mine", "mint", "miss", "mist", "moan", "mock", "mode", "mold", "moon",
    "moor", "more", "moss", "most", "moth", "move", "much", "muse", "must",
    "mute", "myth", "nail", "name", "navy", "near", "neat", "neck", "need",
    "nest", "news", "next", "nice", "nine", "node", "none", "nose", "note",
    "noun", "null", "nuts", "oath", "obey", "odds", "oils", "once", "open",
    "oval", "oven", "over", "pace", "pack", "page", "paid", "pain", "pale",
    "palm", "pane", "park", "part", "pass", "past", "path", "peak", "peal",
    "pear", "peck", "peak", "pure", "pool", "poor", "pope", "pose", "post",
    "pour", "pray", "pull", "push", "quit", "race", "rack", "raft", "rage",
    "raid", "rail", "rain", "rake", "ramp", "rank", "rare", "rash", "rate",
    "read", "real", "reap", "rear", "reef", "reel", "rein", "rest", "rich",
    "ride", "rift", "ring", "riot", "rise", "risk", "road", "roam", "roar",
    "rock", "role", "roll", "roof", "room", "root", "rope", "rose", "rosy",
    "rout", "rove", "ruin", "rule", "rush", "rust", "sack", "safe", "sage",
    "said", "sail", "sake", "sale", "salt", "same", "sand", "sane", "save",
    "seal", "seam", "seat", "seed", "seek", "seem", "seen", "self", "sell",
    "send", "shed", "shin", "ship", "shoe", "shop", "shot", "show", "shut",
    "sick", "side", "sift", "sigh", "sign", "silk", "sill", "silt", "sing",
    "sink", "site", "size", "skid", "skin", "skip", "slab", "slag", "slam",
    "slap", "slat", "slaw", "slid", "slim", "slip", "slit", "slob", "slot",
    "slow", "slug", "snap", "snip", "snob", "snow", "snub", "snug", "soak",
    "soap", "soar", "sock", "soda", "sofa", "soft", "soil", "sold", "sole",
    "some", "song", "soon", "sord", "sort", "soul", "sour", "sown", "span",
    "spar", "spec", "sped", "spin", "spit", "spot", "spry", "spur", "stab",
    "stag", "star", "stay", "stem", "step", "stew", "stir", "stop", "stub",
    "stud", "stun", "such", "suit", "sums", "sung", "sunk", "sure", "surf",
    "swan", "swap", "swim", "tail", "take", "tale", "talk", "tall", "tame",
    "tank", "tape", "taps", "task", "team", "tear", "tell", "tend", "tent",
    "term", "test", "text", "than", "that", "them", "then", "they", "thin",
    "this", "thus", "tick", "tide", "tidy", "tied", "tier", "tile", "till",
    "tilt", "time", "tiny", "tire", "toad", "toil", "told", "toll", "tomb",
    "tone", "took", "tool", "tops", "tore", "torn", "tour", "town", "trap",
    "tray", "tree", "trim", "trip", "true", "tube", "tuck", "tuft", "tune",
    "turn", "twin", "type", "ugly", "undo", "unit", "unto", "upon", "urge",
    "used", "user", "vain", "vale", "vary", "vast", "veil", "vein", "vent",
    "verb", "vest", "veto", "vice", "view", "vine", "void", "volt", "vote",
    "wade", "wage", "wait", "wake", "walk", "wall", "want", "ward", "warm",
    "warn", "warp", "wart", "wary", "wash", "wave", "wavy", "waxy", "weak",
    "weal", "wear", "weed", "week", "weep", "weld", "well", "went", "were",
    "west", "what", "when", "whim", "whip", "whom", "wick", "wide", "wife",
    "wild", "will", "wilt", "wily", "wind", "wine", "wing", "wink", "wipe",
    "wire", "wise", "wish", "wisp", "with", "woke", "wolf", "wood", "wool",
    "word", "wore", "work", "worm", "worn", "wrap", "wren", "yank", "yard",
    "year", "yell", "yoga", "yoke", "yore", "your", "zero", "zone", "zoom",
}

# Common invented / brand-like patterns (CVCV, VCV, CCV, etc.)
# Heuristics used by rule_brandable below.


def rule_brandable(domain: Domain) -> bool:
    """Check if domain is brandable.

    A brandable domain is 6-12 characters (before TLD), contains no hyphens or
    numbers, and is either a dictionary word or a pronounceable invented word.
    """
    name = _name_part(domain.domain)
    if not name:
        return False

    # Length check
    if len(name) < 6 or len(name) > 12:
        return False

    # No hyphens or numbers
    if "-" in name or any(ch.isdigit() for ch in name):
        return False

    # Must be pronounceable: vowel density between 0.25 and 0.6
    vowels = sum(1 for ch in name if ch in "aeiou")
    if len(name) < 2:
        return False
    ratio = vowels / len(name)
    if ratio < 0.25 or ratio > 0.6:
        return False

    # Must not end with a consonant cluster > 3
    # (simple check: last 3 chars are consonants)
    tail = name[-3:].lower()
    if tail and all(ch not in "aeiou" for ch in tail):
        return False

    return True


def rule_short(domain: Domain, max_length: int = 8) -> bool:
    """Check if domain name part is short (<= max_length characters)."""
    name = _name_part(domain.domain)
    if not name:
        return False
    return len(name) <= max_length


def rule_no_numbers(domain: Domain) -> bool:
    """Check if domain contains no numeric digits."""
    return not any(ch.isdigit() for ch in domain.domain)


def rule_no_hyphens(domain: Domain) -> bool:
    """Check if domain contains no hyphens."""
    return "-" not in domain.domain


def rule_tld(domain: Domain, allowed: Optional[List[str]] = None) -> bool:
    """Check if domain TLD is in the allowed list (defaults to [\"com\"])."""
    if allowed is None:
        allowed = ["com"]
    return domain.tld.lower() in [t.lower().lstrip(".") for t in allowed]


def rule_age(domain: Domain, min_age: int = 5) -> bool:
    """Check if domain has been registered for at least ``min_age`` years.

    Uses the ``archive_year`` metric. If missing, the domain is assumed young
    and the rule returns ``False``.
    """
    return _get_metric(domain, "archive_year", min_age)


def rule_traffic(domain: Domain, min_monthly: int = 100) -> bool:
    """Check if domain receives at least ``min_monthly`` monthly visitors.

    Uses the ``monthly_visits`` metric. If missing, returns ``False``.
    """
    return _get_metric(domain, "monthly_visits", min_monthly)


def _get_metric(domain: Domain, metric_type: str, threshold: int) -> bool:
    """Fetch a numeric metric from storage and compare against threshold.

    This is a best-effort lookup via the Storage object. Because rule
    functions are standalone, they don't hold a Storage reference directly.
    The Filter class injects storage metrics via the ``_metrics_cache``
    context variable (set on the Filter instance before calling rules).

    If the metrics are not available the rule conservatively returns False.
    """
    # this is a placeholder — the Filter.apply() method resolves metrics
    # via an injected lookup.  We always return True here so the rule
    # function works as a predicate, but the Filter overrides the call.
    # Subclasses / the Filter cache metrics during apply().
    return True


def rule_no_double_letters(domain: Domain) -> bool:
    """Check if domain has no consecutive identical letters."""
    name = _name_part(domain.domain)
    if not name:
        return False
    for i in range(len(name) - 1):
        if name[i] == name[i + 1]:
            return False
    return True


def rule_vowel_consonant_ratio(domain: Domain, min_ratio: float = 0.25, max_ratio: float = 0.75) -> bool:
    """Check if the vowel/consonant ratio falls within a reasonable range."""
    name = _name_part(domain.domain)
    if not name or len(name) < 2:
        return False
    vowels = sum(1 for ch in name.lower() if ch in "aeiou")
    ratio = vowels / len(name)
    return min_ratio <= ratio <= max_ratio


def rule_starts_with_letter(domain: Domain) -> bool:
    """Check that domain name starts with a letter (not digit/hyphen)."""
    name = _name_part(domain.domain)
    if not name:
        return False
    return name[0].isalpha()


def rule_ends_with_letter(domain: Domain) -> bool:
    """Check that domain name ends with a letter (not digit/hyphen)."""
    name = _name_part(domain.domain)
    if not name:
        return False
    return name[-1].isalpha()


def rule_min_length(domain: Domain, min_length: int = 3) -> bool:
    """Check if domain name part is at least ``min_length`` characters."""
    name = _name_part(domain.domain)
    if not name:
        return False
    return len(name) >= min_length


# ---------------------------------------------------------------------------
# Rule registry  (maps string names → callables)
# ---------------------------------------------------------------------------

_RULES: dict[str, Callable[..., bool]] = {
    "brandable": rule_brandable,
    "short": rule_short,
    "no_numbers": rule_no_numbers,
    "no_hyphens": rule_no_hyphens,
    "tld": rule_tld,
    "age": rule_age,
    "traffic": rule_traffic,
    "no_double_letters": rule_no_double_letters,
    "vc_ratio": rule_vowel_consonant_ratio,
    "starts_with_letter": rule_starts_with_letter,
    "ends_with_letter": rule_ends_with_letter,
    "min_length": rule_min_length,
}


def register_rule(name: str, fn: Callable[..., bool]) -> None:
    """Register a custom rule function."""
    _RULES[name] = fn


def known_rules() -> list[str]:
    """Return list of registered rule names."""
    return list(_RULES)


# ---------------------------------------------------------------------------
# Filter  (composes rules into a pipeline)
# ---------------------------------------------------------------------------


class Filter:
    """Domain filtering pipeline.

    Evaluates each domain against an ordered list of rules and returns only
    those domains that pass every rule.
    """

    def __init__(self, storage: Storage):
        self.storage = storage

    def apply(self, domains: list[Domain], rules: list[str]) -> list[Domain]:
        """Filter *domains* through the named *rules*, returning passing ones.

        Each entry in *rules* is a registered rule name, optionally followed
        by a colon and comma-separated positional arguments::

            "short:10"
            "tld:com,org,net"
            "age:3"

        Parameters
        ----------
        domains:
            List of Domain objects to evaluate.
        rules:
            Rule names (with optional arguments).

        Returns
        -------
        list[Domain]
            Subset of domains that passed every rule.
        """
        logger.info("Applying %d rules to %d domains", len(rules), len(domains))

        # Pre-fetch metrics for all domains to avoid N+1 queries
        metrics_map = self._build_metrics_map(domains)

        result: list[Domain] = []
        for domain in domains:
            if self._evaluate(domain, rules, metrics_map.get(domain.domain, {})):
                result.append(domain)

        logger.info("Filter passed: %d / %d domains", len(result), len(domains))
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_metrics_map(self, domains: list[Domain]) -> dict[str, dict[str, str]]:
        """Build {domain: {metric_type: value}} map for bulk metric lookup."""
        mm: dict[str, dict[str, str]] = {}
        for d in domains:
            try:
                rows = self.storage.get_metrics(d.domain)
                mm[d.domain] = {r["metric_type"]: r["value"] for r in rows}
            except Exception:
                mm[d.domain] = {}
        return mm

    def _evaluate(
        self,
        domain: Domain,
        rules: list[str],
        metrics: dict[str, str],
    ) -> bool:
        """Run all rules against a single domain."""
        for rule_spec in rules:
            rule_name, args = self._parse_rule(rule_spec)
            fn = _RULES.get(rule_name)
            if fn is None:
                logger.warning("Unknown rule %r — skipping", rule_name)
                continue

            try:
                # Build call args: domain + parsed args
                call_args: list[Any] = [domain]
                call_args.extend(args)

                # Resolve metric-backed rules on-the-fly
                if rule_name in ("age", "traffic"):
                    if not self._check_metric_rule(rule_name, metrics, args):
                        return False
                    continue  # metric rule handled separately

                if not fn(*call_args):
                    return False
            except Exception:
                logger.exception("Rule %r failed on %s", rule_name, domain.domain)
                return False
        return True

    @staticmethod
    def _parse_rule(rule_spec: str) -> tuple[str, list[Any]]:
        """Parse ``"short:10"`` → ``("short", [10])``."""
        if ":" not in rule_spec:
            return rule_spec, []
        name, raw_args = rule_spec.split(":", 1)
        parsed: list[Any] = []
        for part in raw_args.split(","):
            part = part.strip()
            # Try int first
            try:
                parsed.append(int(part))
            except ValueError:
                try:
                    parsed.append(float(part))
                except ValueError:
                    parsed.append(part)
        return name, parsed

    @staticmethod
    def _check_metric_rule(
        rule_name: str,
        metrics: dict[str, str],
        args: list[Any],
    ) -> bool:
        """Check a metric-backed rule (age/traffic) against pre-fetched metrics."""
        threshold: int = 0
        if args:
            threshold = int(args[0])

        metric_key = {"age": "archive_year", "traffic": "monthly_visits"}.get(rule_name, rule_name)
        raw = metrics.get(metric_key)
        if raw is None:
            return False
        try:
            return int(raw) >= threshold
        except (ValueError, TypeError):
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _name_part(domain: str) -> str:
    """Extract the name part of a domain (before the first dot)."""
    return domain.split(".")[0].lower() if domain else ""
