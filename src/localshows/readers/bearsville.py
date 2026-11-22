"""Bearsville Theater lists every show on its home page."""

from datetime import date

from bs4 import BeautifulSoup

from localshows.config import Venue
from localshows.models import Listing
from localshows.readers.common import clock, date_without_year, text_of
from localshows.web import ReadError, Web


def extract(page: str, venue: Venue, today: date) -> list[Listing]:
    soup = BeautifulSoup(page, "html.parser")
    listings = []
    # The slideshow and featured strip repeat shows from the main list.
    for card in soup.select(".bv-event-wrapper.bv-default-list"):
        if card.find_parent(class_="bv-events-slide"):
            continue
        link = card.select_one(".bv-event-title a")
        if not link:
            raise ReadError("a Bearsville card has no title")
        day = date_without_year(
            text_of(card.select_one(".bv-event-weekday")),
            text_of(card.select_one(".bv-event-monthday")),
            today,
        )
        listings.append(
            Listing(
                venue=venue.id,
                day=day,
                start=clock(text_of(card.select_one(".bv-event-show"))),
                title=text_of(link),
                url=link["href"],
                support=text_of(card.select_one(".bv-event-description")),
            )
        )
    if not listings:
        raise ReadError("no show cards found on Bearsville's page")
    return listings


def read(venue: Venue, web: Web, today: date) -> list[Listing]:
    return extract(web.get(venue.url), venue, today)
