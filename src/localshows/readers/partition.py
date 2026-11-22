"""The Partition's events page (Wix Events), which embeds its events as JSON."""

import json
from collections.abc import Iterator
from datetime import date, datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from localshows.config import Venue
from localshows.models import Listing
from localshows.web import ReadError, Web


def _event_lists(value) -> Iterator[dict]:
    if isinstance(value, dict):
        if isinstance(value.get("events"), list) and "hasMore" in value:
            yield value
        for child in value.values():
            yield from _event_lists(child)
    elif isinstance(value, list):
        for child in value:
            yield from _event_lists(child)


def extract(page: str, venue: Venue) -> list[Listing]:
    found = []
    for tag in BeautifulSoup(page, "html.parser").select('script[type="application/json"]'):
        try:
            found += _event_lists(json.loads(tag.string or ""))
        except ValueError:
            continue
    # An empty list is normal here, but a missing one means the page changed.
    if not found:
        raise ReadError("no events list found on The Partition's page")
    listings = []
    for block in found:
        if block["hasMore"]:
            raise ReadError("The Partition's page no longer holds the whole list")
        for event in block["events"]:
            try:
                when = event["scheduling"]["config"]
                if when.get("scheduleTbd"):
                    continue
                starts = datetime.fromisoformat(when["startDate"]).astimezone(
                    ZoneInfo(when.get("timeZoneId") or "America/New_York")
                )
                title = event["title"]
            except (KeyError, TypeError, ValueError) as error:
                raise ReadError("The Partition's event data has changed shape") from error
            listings.append(
                Listing(
                    venue=venue.id,
                    day=starts.date(),
                    start=starts.time().replace(tzinfo=None),
                    title=title,
                    url=venue.url,
                    description=event.get("description") or "",
                )
            )
    return listings


def read(venue: Venue, web: Web, today: date) -> list[Listing]:
    return extract(web.get(venue.url), venue)
