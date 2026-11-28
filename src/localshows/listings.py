"""Collect the next 12 months of shows from every venue."""

from dataclasses import dataclass, field
from datetime import date, timedelta

from localshows import billing, details
from localshows.config import Venue
from localshows.models import Show
from localshows.readers import READERS
from localshows.web import ReadError, Web

WINDOW = timedelta(days=365)


@dataclass
class Collected:
    shows: list[Show] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    # Show pages that couldn't be read for a write-up, per venue (not a failure).
    no_write_up: dict[str, int] = field(default_factory=dict)


def collect(venues: list[Venue], web: Web, today: date, write_ups: bool = False) -> Collected:
    result, listings = Collected(), []
    for venue in venues:
        try:
            found = READERS[venue.reader](venue, web, today)
        except ReadError as error:
            result.failures[venue.id] = str(error)
        except Exception as error:  # one broken venue mustn't stop the others
            result.failures[venue.id] = f"reader broke: {type(error).__name__}: {error}"
        else:
            upcoming = [item for item in found if today <= item.day <= today + WINDOW]
            result.counts[venue.id] = len(upcoming)
            if write_ups:
                upcoming, missing = details.add_write_ups(upcoming, venue.reader, web)
                if missing:
                    result.no_write_up[venue.id] = missing
            listings += upcoming
    result.shows = billing.parse_all(listings)
    return result
