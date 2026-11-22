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


def load_venues(root: Path) -> list[Venue]:
    path = root / "config" / "venues.json"
    venues = [Venue(**row) for row in json.loads(path.read_text(encoding="utf-8"))]
    ids = [venue.id for venue in venues]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate venue id in {path}")
    return venues
