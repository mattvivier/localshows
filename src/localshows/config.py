"""The venue list."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Venue:
    id: str
    name: str
    town: str
    reader: str
    url: str
    # A rough ceiling on a playing artist's Spotify followers, from the size of the room;
    # an artist far above it is almost certainly a namesake. Evidence, never proof.
    followers_max: int | None = None
    # And a floor for headliners, who draw a crowd. Openers can be anyone.
    headliner_min_followers: int = 0


def load_venues(root: Path) -> list[Venue]:
    path = root / "config" / "venues.json"
    venues = [Venue(**row) for row in json.loads(path.read_text(encoding="utf-8"))]
    ids = [venue.id for venue in venues]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate venue id in {path}")
    return venues
