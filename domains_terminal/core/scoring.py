"""Domain scoring engine.

Purpose: Produce normalized 0-100 scores across 6 dimensions (brandability,
mnemonic, length, TLD value, keywords, pronounceable). Each dimension returns
a ``Score`` model. Composite score is a weighted average.

Input: List[Domain] from storage, optional weight overrides
Output: List[Score] persisted to storage
Dependencies: domains_terminal.models.Domain, domains_terminal.storage.Storage
Side effects: Writes Score rows to SQLite"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from domains_terminal.models import Domain, Score
from domains_terminal.storage import Storage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score weights — used when aggregating into a composite score
# ---------------------------------------------------------------------------
# Sub-classes / callers can override via ScoringEngine(weights={...})
DEFAULT_WEIGHTS: Dict[str, float] = {
    "brandability": 0.25,
    "mnemonic": 0.15,
    "length": 0.20,
    "tld_value": 0.15,
    "keywords": 0.15,
    "pronounceable": 0.10,
}

# TLD → base value (0-100) lookup
TLD_VALUES: Dict[str, int] = {
    "com": 100,
    "org": 75,
    "net": 70,
    "io": 60,
    "co": 55,
    "ai": 50,
    "app": 50,
    "dev": 50,
    "com.au": 45,
    "co.uk": 45,
    "me": 45,
    "info": 40,
    "biz": 35,
    "us": 35,
    "uk": 35,
    "de": 35,
    "ca": 35,
    "eu": 35,
    "in": 30,
    "xyz": 20,
    "top": 15,
    "club": 15,
    "online": 15,
    "site": 15,
    "icu": 10,
    "tk": 5,
    "ml": 5,
    "ga": 5,
}


def normalize_score(raw: int, min_val: int, max_val: int) -> int:
    """Clamp *raw* to [0, 100] based on the range [min_val, max_val].

    Values below min_val → 0; above max_val → 100.
    """
    if max_val <= min_val:
        return 50  # degenerate range → mid
    clamped = max(min_val, min(max_val, raw))
    return int((clamped - min_val) / (max_val - min_val) * 100)


# ---------------------------------------------------------------------------
# Scoring engine
# ---------------------------------------------------------------------------


class ScoringEngine:
    """Multi-dimensional domain scoring engine.

    Each ``score_*`` method returns a ``Score`` object with a 0-100 value and
    an estimated confidence.  The top-level ``score()`` method runs a
    configurable subset of these dimensions and persists the results via
    ``Storage``.
    """

    def __init__(self, storage: Storage, weights: Optional[Dict[str, float]] = None):
        self.storage = storage
        self.weights = weights or dict(DEFAULT_WEIGHTS)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, domain: Domain, rules: Optional[List[str]] = None) -> List[Score]:
        """Run scoring dimensions against *domain*.

        Parameters
        ----------
        domain:
            The domain to score.
        rules:
            Subset of dimension names to evaluate (e.g. ``["brandability",
            "length", "tld_value"]``).  When ``None`` all registered
            dimensions are evaluated.

        Returns
        -------
        List[Score]
            One ``Score`` per evaluated dimension.
        """
        if rules is None:
            rules = list(self.weights)

        results: List[Score] = []
        for rule in rules:
            scorer = getattr(self, f"score_{rule}", None)
            if scorer is None:
                logger.warning("Unknown scoring dimension %r — skipping", rule)
                continue
            try:
                score = scorer(domain)
                results.append(score)
            except Exception:
                logger.exception("score_%s failed for %s", rule, domain.domain)

        # Persist scores
        for s in results:
            try:
                self.storage.insert_score(s.model_dump(exclude={"id"}))
            except Exception:
                logger.exception("Failed to persist score for %s", domain.domain)

        return results

    # ------------------------------------------------------------------
    # Scoring dimensions
    # ------------------------------------------------------------------

    def score_brandability(self, domain: Domain) -> Score:
        """Score how brandable the domain is (0-100).

        Factors:
            - Length 6-10 is ideal
            - No hyphens
            - No numbers
            - Vowel density 0.25-0.55 (pronounceable)
            - No awkward consonant clusters
        """
        name = _name_part(domain.domain)
        if not name:
            return Score(domain=domain.domain, rule="brandability", score=0, confidence=0.5)

        points = 100

        # --- Length penalty ------------------------------------------------
        length = len(name)
        if length < 5:
            points -= 30
        elif length < 6:
            points -= 10
        elif 6 <= length <= 10:
            pass  # ideal range
        elif length <= 12:
            points -= 10
        else:
            points -= 30

        # --- Hyphens -------------------------------------------------------
        if "-" in name:
            points -= 40

        # --- Numbers -------------------------------------------------------
        if any(ch.isdigit() for ch in name):
            points -= 30

        # --- Vowel density -------------------------------------------------
        vowels = sum(1 for ch in name if ch in "aeiou")
        if len(name) > 0:
            v_ratio = vowels / len(name)
            if v_ratio < 0.20:
                points -= 25
            elif v_ratio < 0.25:
                points -= 10
            elif 0.25 <= v_ratio <= 0.55:
                pass  # ideal
            elif v_ratio <= 0.65:
                points -= 5
            else:
                points -= 15

        # --- Consonant clusters at end -------------------------------------
        tail = name[-3:].lower()
        if tail and all(ch not in "aeiou" for ch in tail):
            points -= 15

        # --- Dictionary word bonus -----------------------------------------
        if name in _COMMON_WORDS:
            points += 5

        score_val = max(0, min(100, points))
        confidence = _confidence_from_length(length, 0.6, 0.9)
        return Score(domain=domain.domain, rule="brandability", score=score_val, confidence=confidence)

    def score_mnemonic(self, domain: Domain) -> Score:
        """Score memorability (0-100).

        Factors:
            - Repeated letters (double letters are memorable)
            - Alternating vowel-consonant pattern (easy to remember)
            - Short length (easier to recall)
            - Repetitive sounds (assonance)
        """
        name = _name_part(domain.domain)
        if not name:
            return Score(domain=domain.domain, rule="mnemonic", score=0, confidence=0.5)

        points = 50  # start neutral

        length = len(name)
        if length <= 5:
            points += 15  # very short → memorable
        elif length <= 8:
            points += 10
        elif length >= 15:
            points -= 15

        # Double-letter bonus (e.g., "doodle", "buzzy")
        if re.search(r"(.)\1", name):
            points += 15

        # Alternating vowel-consonant pattern (CVCV, VCV) bonus
        if _is_alternating(name):
            points += 10

        # Assonance bonus (same vowel repeated)
        vowel_set = set(ch for ch in name if ch in "aeiou")
        if len(vowel_set) == 1 and len(name) >= 3:
            points += 10

        # Simple consonant structure bonus (few consonant clusters)
        clusters = len(re.findall(r"[^aeiou]{3,}", name))
        points -= clusters * 5

        # Starts-with-letter (digits at start hurt memorability)
        if name and name[0].isalpha():
            points += 5
        elif name and name[0].isdigit():
            points -= 10

        score_val = max(0, min(100, points))
        confidence = _confidence_from_length(length, 0.5, 0.8)
        return Score(domain=domain.domain, rule="mnemonic", score=score_val, confidence=confidence)

    def score_length(self, domain: Domain) -> Score:
        """Score domain-name length (0-100).  6-8 characters is optimal."""
        name = _name_part(domain.domain)
        if not name:
            return Score(domain=domain.domain, rule="length", score=0, confidence=0.5)

        length = len(name)
        scores_map = {
            3: 60, 4: 70, 5: 85,
            6: 100, 7: 100, 8: 100,
            9: 85, 10: 75, 11: 60,
            12: 50, 13: 40, 14: 30,
        }
        points = scores_map.get(length)
        if points is not None:
            score_val = points
        elif length < 3:
            score_val = 30
        else:
            score_val = max(0, 100 - (length - 8) * 8)

        confidence = _confidence_from_length(length, 0.8, 1.0)
        return Score(domain=domain.domain, rule="length", score=score_val, confidence=confidence)

    def score_tld_value(self, domain: Domain) -> Score:
        """Score the domain's TLD extension (0-100).

        Uses a built-in TLD value lookup.  Unknown TLDs get a default of 15.
        """
        tld = domain.tld.lower().lstrip(".")
        points = TLD_VALUES.get(tld, 15)
        score_val = max(0, min(100, points))
        confidence = 0.7 if tld in TLD_VALUES else 0.3
        return Score(domain=domain.domain, rule="tld_value", score=score_val, confidence=confidence)

    def score_keywords(self, domain: Domain) -> Score:
        """Score keyword richness (0-100).

        Factors:
            - Multi-word domains (via word_count field) get a boost
            - Exact dictionary word match is a strong signal
            - Domain contains meaningful English substrings
        """
        name = _name_part(domain.domain)
        if not name:
            return Score(domain=domain.domain, rule="keywords", score=0, confidence=0.5)

        points = 30  # baseline

        # Exact dictionary word match
        if name in _COMMON_WORDS:
            points += 40
        else:
            # Partial dictionary match: count how many dictionary words
            # are substrings of the name
            matched = sum(1 for w in _COMMON_WORDS if len(w) >= 3 and w in name)
            points += min(30, matched * 5)

        # Multi-word domains
        if domain.word_count > 1:
            points += 15

        # Length bonus for keyword phrases (7-14 chars)
        length = len(name)
        if 7 <= length <= 14:
            points += 10

        score_val = max(0, min(100, points))
        confidence = _confidence_from_length(length, 0.4, 0.7)
        return Score(domain=domain.domain, rule="keywords", score=score_val, confidence=confidence)

    def score_pronounceable(self, domain: Domain) -> Score:
        """Score pronounceability (0-100).

        A pronounceable domain is easy to say aloud — crucial for word-of-mouth
        and brand recall.
        """
        name = _name_part(domain.domain)
        if not name or len(name) < 2:
            return Score(domain=domain.domain, rule="pronounceable", score=0, confidence=0.5)

        points = 70  # start high

        # Vowel ratio
        vowels = sum(1 for ch in name if ch in "aeiou")
        v_ratio = vowels / len(name)

        if v_ratio < 0.2:
            points -= 40  # unpronounceable (e.g., "tmsrf")
        elif v_ratio < 0.3:
            points -= 20
        elif 0.3 <= v_ratio <= 0.55:
            points += 10  # ideal
        elif v_ratio > 0.7:
            points -= 10  # too vowel-heavy

        # Penalise long consonant clusters
        clusters_3 = len(re.findall(r"[^aeiou]{3,}", name))
        points -= clusters_3 * 10

        clusters_4 = len(re.findall(r"[^aeiou]{4,}", name))
        points -= clusters_4 * 10  # extra penalty for very long clusters

        # Vowel-start bonus (easier to say)
        if name and name[0] in "aeiou":
            points += 5

        # Double-consonant penalty (harder to pronounce)
        if re.search(r"([^aeiou])\1", name):
            points -= 5

        # Penalise endings with "ngly", "ght", etc.
        if re.search(r"(ngly|ght|tch|dge)$", name):
            points -= 5

        score_val = max(0, min(100, points))
        confidence = _confidence_from_length(len(name), 0.5, 0.8)
        return Score(domain=domain.domain, rule="pronounceable", score=score_val, confidence=confidence)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _name_part(domain: str) -> str:
    """Return the name portion (before the first dot)."""
    return domain.split(".")[0].lower() if domain else ""


def _confidence_from_length(length: int, low_conf: float, high_conf: float) -> float:
    """Produce a confidence value proportional to domain-name length.

    Very short (< 3) or empty names get low confidence; names >= 6 get maximum
    confidence (because we have more signal to score).
    """
    if length >= 6:
        return high_conf
    if length <= 2:
        return low_conf
    # Linear interpolation between low_conf and high_conf
    ratio = (length - 2) / (6 - 2)
    return low_conf + (high_conf - low_conf) * ratio


def _is_alternating(name: str) -> bool:
    """Check if the name has a mostly alternating vowel-consonant pattern.

    E.g. ``"bode"`` (C-V-C-V) → True,  ``"synd"`` (C-C-C-C) → False.
    """
    if len(name) < 3:
        return False
    v = set("aeiou")
    # Count transitions
    transitions = 0
    for i in range(len(name) - 1):
        c1 = name[i] in v
        c2 = name[i + 1] in v
        if c1 != c2:
            transitions += 1
    # At least 50% of adjacent pairs should alternate
    return transitions / (len(name) - 1) >= 0.5


# Reuse dictionary words from filter module
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
