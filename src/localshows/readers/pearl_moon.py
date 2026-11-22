"""Pearl Moon's events page (SpotHopper)."""

from datetime import date, time

from bs4 import BeautifulSoup

from localshows.config import Venue
from localshows.models import Listing
from localshows.readers.common import text_of
from localshows.web import ReadError, Web


def extract(page: str, venue: Venue) -> list[Listing]:
    soup = BeautifulSoup(page, "html.parser")
    listings = []
    for card in soup.select(".event-calendar-card"):
        try:
            day = date.fromisoformat(card["data-event-start-date"][:10])
        except (KeyError, ValueError) as error:
            raise ReadError("a Pearl Moon card has no date") from error
        start = card.get("data-event-start-time")
        listings.append(
            Listing(
                venue=venue.id,
                day=day,
                start=time.fromisoformat(start.zfill(5)) if start else None,
                title=text_of(card.h2),
                url=venue.url,
                description=text_of(card.select_one(".event-info-text")),
            )
        )
    if not listings:
        raise ReadError("no event cards found on Pearl Moon's page")
    return listings


def read(venue: Venue, web: Web, today: date) -> list[Listing]:
    return extract(web.get(venue.url), venue)
