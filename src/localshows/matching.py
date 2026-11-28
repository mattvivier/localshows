"""Find each act's Spotify artist: fuzzy name match, then clues to tell namesakes apart.

Every clue belongs to one specific Spotify artist, never just to the name:
  - people the venue's write-up names who are credited in that artist's catalog
    (band members' own projects, regular guests, that night's opener);
  - album or song titles the write-up names that are in that artist's catalog;
  - whether that artist's following fits the size of the room (evidence against only);
  - whether that artist is still putting records out (breaks an otherwise even tie).
When the clues don't single out one artist, the act is left unsure rather than guessed.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from localshows.fuzzy import MATCH, Candidate, Match, best_match, normalize, similarity
from localshows.models import Act

PAGES = 2
ACTIVE = timedelta(days=6 * 365)
MOST_TIED = 6
# Titles too common to tell anyone apart.
GENERIC = {
    "live", "intro", "outro", "interlude", "christmas", "greatest hits", "the best of",
    "silent night", "white christmas", "jingle bells", "auld lang syne", "happy birthday",
    "amazing grace", "hallelujah", "o holy night", "let it snow", "winter wonderland",
    "have yourself a merry little christmas", "the christmas song", "live at the",
}  # fmt: skip

_THE_BAND = re.compile(r"^the\s+|\s+band$", re.I)
_VERSION = re.compile(r"\s*(?:\([^)]*\)|\[[^\]]*\]|\s-\s.*)\s*$")


@dataclass
class Context:
    """What the venues say about an act's shows, and how big those rooms are."""

    text: str = ""
    # (follower ceiling or None, follower floor) for each show the act plays.
    rooms: list[tuple[int | None, int]] = field(default_factory=list)


@dataclass
class Clues:
    people: list[str] = field(default_factory=list)
    titles: list[str] = field(default_factory=list)
    followers: int | None = None
    fits: bool | None = None  # None: no follower count, or no room size known
    active: bool | None = None

    @property
    def named(self) -> int:
        return len(self.people) + len(self.titles)


@dataclass
class ArtistMatch:
    act: str
    status: str  # "matched", "unsure" or "none"
    artist: Candidate | None = None
    name_used: str = ""
    how: str = ""
    candidates: tuple[Candidate, ...] = ()
    clues: dict[str, Clues] = field(default_factory=dict)


def song_title(title: str) -> str:
    """'Ophelia - 2000 Remaster' and 'Ophelia (Live)' are both 'ophelia'."""
    short, previous = title, None
    while previous != short:
        previous, short = short, _VERSION.sub("", short)
    return normalize(short or title)


def same_song(a: str, b: str) -> bool:
    return similarity(song_title(a), song_title(b)) >= MATCH


def _phrase_in(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


def fits_room(followers: int | None, rooms: list[tuple[int | None, int]]) -> bool | None:
    if followers is None or not rooms:
        return None
    return any(
        (ceiling is None or followers <= ceiling) and followers >= floor for ceiling, floor in rooms
    )


def _search(act: Act, spotify) -> tuple[str, Match]:
    names = [act.name] if act.tribute else [act.name, *act.also]
    fallback: tuple[str, Match] = (act.name, Match("none"))
    for name in names:
        pool: list[Candidate] = []
        # Search ranks "Marc Black" low for "The Marc Black Band", so try the bare name too.
        queries = [q for q in dict.fromkeys([name, _THE_BAND.sub("", name).strip()]) if q]
        for query in queries:
            for page in range(PAGES):
                found = spotify.search_artists(query, page)
                pool += found
                match = best_match([name], pool, exact_only=act.tribute)
                if match.score >= MATCH or len(found) < 10:
                    break
            if match.score >= MATCH:
                break
        if match.score >= MATCH:
            return name, match
        if fallback[1].status == "none" and match.status != "none":
            fallback = (name, match)
    return fallback


def gather_clues(
    candidates: tuple[Candidate, ...], act: Act, context: Context, spotify, today: date,
    catalogs: bool,
) -> dict[str, Clues]:  # fmt: skip
    own_names = [act.name, *act.also]
    clues = {}
    for candidate in candidates:
        followers = spotify.followers.get(candidate.id)
        clues[candidate.id] = Clues(followers=followers, fits=fits_room(followers, context.rooms))
    text = normalize(context.text)
    if not catalogs:
        return clues

    def own(name: str) -> bool:
        return any(similarity(name, mine) >= MATCH for mine in own_names)

    found: dict[str, tuple[set[str], set[str]]] = {}
    for candidate in candidates:
        catalog = spotify.catalog(candidate.id)
        if catalog.latest:
            clues[candidate.id].active = catalog.latest >= today - ACTIVE
        titles = {song_title(t) for t in catalog.titles}
        titles = {t for t in titles if len(t.split()) >= 2 and len(t) >= 8 and t not in GENERIC}
        people = {normalize(p) for p in catalog.people}
        people = {p for p in people if len(p.split()) >= 2}
        found[candidate.id] = (
            {t for t in titles if text and _phrase_in(text, t) and not own(t)},
            {p for p in people if text and _phrase_in(text, p) and not own(p)},
        )
    # A title or person every namesake shares (a cover of a standard) tells nothing.
    shared = Counter(x for titles, people in found.values() for x in titles | people)
    for candidate_id, (titles, people) in found.items():
        clues[candidate_id].titles = sorted(t for t in titles if shared[t] == 1)
        clues[candidate_id].people = sorted(p for p in people if shared[p] == 1)
    return clues


def _decide(result: ArtistMatch, candidates: tuple[Candidate, ...]) -> None:
    clues = result.clues
    by_id = {c.id: c for c in candidates}

    def pick(candidate_id: str, how: str) -> None:
        result.status, result.artist, result.how = "matched", by_id[candidate_id], how

    named = sorted(candidates, key=lambda c: -clues[c.id].named)
    if clues[named[0].id].named and (
        len(named) == 1 or clues[named[0].id].named > clues[named[1].id].named
    ):
        return pick(named[0].id, "the venue's write-up names their people or records")
    if len(named) > 1 and clues[named[0].id].named:
        result.status, result.how = "unsure", "the write-up names records of more than one"
        return None
    fitting = [c for c in candidates if clues[c.id].fits is not False]
    if not fitting:
        result.status, result.how = "unsure", "too big or too small for the room"
        return None
    if len(candidates) == 1:
        return pick(candidates[0].id, "name")
    if len(fitting) == 1:
        return pick(
            fitting[0].id, f"the only one of {len(candidates)} same names that fits the room"
        )
    active = [c for c in fitting if clues[c.id].active]
    if len(active) == 1:
        return pick(active[0].id, f"the only one of {len(fitting)} same names still releasing")
    result.status, result.how = "unsure", f"{len(candidates)} same names; nothing tells them apart"
    return None


def match_act(
    act: Act, context: Context, spotify, overrides: dict[str, str | None], today: date
) -> ArtistMatch:
    key = normalize(act.name)
    if key in overrides:
        artist_id = overrides[key]
        if artist_id is None:
            return ArtistMatch(act.name, "none", how="override: skip")
        return ArtistMatch(act.name, "matched", Candidate(artist_id, ""), act.name, "override")

    name, match = _search(act, spotify)
    result = ArtistMatch(act.name, match.status, name_used=name, candidates=match.candidates)
    if match.score < MATCH:
        result.how = "only look-alikes" if match.candidates else "not found"
        return result
    candidates = match.candidates[:MOST_TIED]
    result.candidates = candidates
    # A lone name match that fits the room needs nothing more; anything else, look closer.
    result.clues = gather_clues(candidates, act, context, spotify, today, catalogs=False)
    if len(candidates) > 1 or result.clues[candidates[0].id].fits is False:
        result.clues = gather_clues(candidates, act, context, spotify, today, catalogs=True)
    _decide(result, candidates)
    return result


def overrides_from(raw: dict[str, str | None]) -> dict[str, str | None]:
    """The overrides file maps an act's billed name to a Spotify artist ID, or null to skip."""
    return {normalize(name): value for name, value in raw.items() if not name.startswith("_")}
