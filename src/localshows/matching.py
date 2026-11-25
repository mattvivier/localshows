"""Find each act's Spotify artist: fuzzy name match, then songs to settle doubt.

Several artists often share a name exactly (there are many "Whitney"s). Last.fm's
most-played songs for that name pick out which one is meant: it's the artist whose
Spotify catalog has those songs. The same check flags a lone name match whose catalog
has none of them, which is probably a namesake.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from localshows.fuzzy import MATCH, Candidate, Match, best_match, normalize, similarity
from localshows.models import Act

SONGS_TO_CHECK = 5
# Below this many known songs, Last.fm may just be listing the namesake's few plays.
ENOUGH_SONGS = 3
PAGES = 2

_THE_BAND = re.compile(r"^the\s+|\s+band$", re.I)
_VERSION = re.compile(r"\s*(?:\([^)]*\)|\[[^\]]*\]|\s-\s.*)\s*$")


@dataclass
class ArtistMatch:
    act: str
    status: str  # "matched", "unsure" or "none"
    artist: Candidate | None = None
    name_used: str = ""
    # How it was decided, for the report: override, name, songs, ...
    how: str = ""
    candidates: tuple[Candidate, ...] = ()
    votes: dict[str, int] = field(default_factory=dict)
    songs_checked: int = 0


def song_title(title: str) -> str:
    """'Ophelia - 2000 Remaster' and 'Ophelia (Live)' are both 'ophelia'."""
    short, previous = title, None
    while previous != short:
        previous, short = short, _VERSION.sub("", short)
    return normalize(short or title)


def same_song(a: str, b: str) -> bool:
    return similarity(song_title(a), song_title(b)) >= MATCH


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


def _votes(name: str, candidates: tuple[Candidate, ...], spotify, lastfm) -> tuple[Counter, int]:
    """For each candidate, how many of the name's top Last.fm songs it has on Spotify."""
    songs = lastfm.top_tracks(name)
    if len(songs) < ENOUGH_SONGS:
        return Counter(), 0
    ids = {candidate.id for candidate in candidates}
    votes: Counter = Counter()
    for song in songs[:SONGS_TO_CHECK]:
        has_it = set()
        for track in spotify.search_tracks(song_title(song) or song, name):
            if same_song(song, track.get("name", "")):
                has_it |= {artist.get("id") for artist in track.get("artists", [])} & ids
        votes.update(has_it)
    return votes, min(len(songs), SONGS_TO_CHECK)


def match_act(act: Act, spotify, lastfm, overrides: dict[str, str | None]) -> ArtistMatch:
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

    votes, checked = _votes(name, match.candidates, spotify, lastfm)
    result.votes, result.songs_checked = dict(votes), checked
    ranked = votes.most_common()
    if len(match.candidates) == 1:
        result.artist = match.candidates[0]
        if not checked:
            result.how = "name (too few Last.fm songs to check)"
        elif votes:
            result.how = "name and songs"
        else:
            result.status, result.how = "unsure", "name matches but none of its top songs do"
    elif ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
        winner = ranked[0][0]
        result.status, result.how = "matched", f"songs, from {len(match.candidates)} same names"
        result.artist = next(c for c in match.candidates if c.id == winner)
    else:
        result.how = f"{len(match.candidates)} same names; songs don't decide"
    return result


def overrides_from(raw: dict[str, str | None]) -> dict[str, str | None]:
    """The overrides file maps an act's billed name to a Spotify artist ID, or null to skip."""
    return {normalize(name): value for name, value in raw.items() if not name.startswith("_")}
