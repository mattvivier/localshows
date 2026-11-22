"""Fuzzy matching for artist and show names.

Plain edit distance is dangerous for this job: "Lez Zeppelin" is 92% similar to
"Led Zeppelin", and tribute acts are named that way on purpose. So differences are
only forgiven when they are of a kind that doesn't change who the act is:

* case, accents, punctuation, "&" for "and", a leading "The"
* spacing, a missing "and" in a list, or "5" for "Five"
* a trailing "Band" on a name of two or more words ("Trio" and "Quartet" name other acts)
* one typo, inside a word of six or more letters, that keeps its first letter

Anything merely similar is reported as unsure and never picked.
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

EXACT = 1.0
REWORDED = 0.98
SUFFIX = 0.95
TYPO = 0.92
MATCH = 0.9
CLOSE = 0.65

_NUMBERS = "zero one two three four five six seven eight nine ten".split()


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"['’‘`​﻿]", "", text.replace("&", " and "))
    words = re.sub(r"[\W_]+", " ", text).split()
    if len(words) > 1 and words[0] == "the":
        words = words[1:]
    return " ".join(words)


def _one_edit(a: str, b: str) -> bool:
    """One insertion, deletion, substitution or swap of neighboring letters."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    if len(a) > len(b):
        return a[i + 1 :] == b[i:]
    if len(b) > len(a):
        return a[i:] == b[i + 1 :]
    return a[i + 1 :] == b[i + 1 :] or (
        a[i : i + 2] == b[i : i + 2][::-1] and a[i + 2 :] == b[i + 2 :]
    )


def _is_typo(a: str, b: str) -> bool:
    return max(len(a), len(b)) >= 6 and a[:1] == b[:1] and _one_edit(a, b)


def _without_band(words: list[str]) -> list[str]:
    return words[:-1] if len(words) >= 3 and words[-1] == "band" else words


def _squashed(words: list[str]) -> str:
    return "".join(
        str(_NUMBERS.index(word)) if word in _NUMBERS else word for word in words if word != "and"
    )


def similarity(a: str, b: str) -> float:
    """Score two names. At or above MATCH means they are the same act."""
    left, right = normalize(a), normalize(b)
    if not left or not right:
        return 0.0
    if left == right:
        return EXACT
    x, y = left.split(), right.split()
    if _squashed(x) and _squashed(x) == _squashed(y):
        return REWORDED
    if _without_band(x) == y or _without_band(y) == x:
        return SUFFIX
    if len(x) == len(y):
        changed = [(p, q) for p, q in zip(x, y, strict=True) if p != q]
        if len(changed) == 1 and _is_typo(*changed[0]):
            return TYPO
    # Scaled so that resemblance alone can never reach MATCH.
    return SequenceMatcher(None, left, right).ratio() * 0.85


def mentions(text: str, name: str) -> bool:
    """Whether text names this act, allowing the same differences as similarity."""
    words, wanted = normalize(text).split(), normalize(name).split()
    size = len(wanted)
    if not size:
        return False
    return any(
        similarity(" ".join(words[i : i + size]), name) >= MATCH
        for i in range(len(words) - size + 1)
    )


def _spelling(name: str) -> str:
    return name.casefold().replace("’", "'").strip()


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str


@dataclass(frozen=True)
class Match:
    status: str  # "matched", "unsure" or "none"
    candidates: tuple[Candidate, ...] = ()
    score: float = 0.0


def best_match(
    names: Sequence[str], candidates: Iterable[Candidate], *, exact_only: bool = False
) -> Match:
    """Pick a candidate for an act's names, which are tried in priority order."""
    pool = list({candidate.id: candidate for candidate in candidates}.values())
    threshold = EXACT if exact_only else MATCH
    close: dict[str, tuple[float, Candidate]] = {}
    for name in names:
        scored = [(similarity(name, candidate.name), candidate) for candidate in pool]
        top = max((score for score, _ in scored), default=0.0)
        if top >= threshold:
            winners = tuple(candidate for score, candidate in scored if score == top)
            # Of "moe.", "MoE" and "M.O.E.", the one punctuated as billed is the act.
            as_billed = tuple(c for c in winners if _spelling(c.name) == _spelling(name))
            if len(as_billed) == 1:
                winners = as_billed
            return Match("matched" if len(winners) == 1 else "unsure", winners, top)
        for score, candidate in scored:
            if score >= CLOSE and score > close.get(candidate.id, (0.0, None))[0]:
                close[candidate.id] = (score, candidate)
    if not close:
        return Match("none")
    ranked = sorted(close.values(), key=lambda pair: -pair[0])[:3]
    return Match("unsure", tuple(candidate for _, candidate in ranked), ranked[0][0])
