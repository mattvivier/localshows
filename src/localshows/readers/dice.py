"""Shared reader for any DICE venue page."""

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from localshows.config import Venue
from localshows.models import Listing
from localshows.web import ReadError, Web

LOCAL_TIME = ZoneInfo("America/New_York")


def extract_events(page: str) -> list[dict]:
    tag = BeautifulSoup(page, "html.parser").select_one("#__NEXT_DATA__")
    try:
        profile = json.loads(tag.string)["props"]["pageProps"]["profile"]
        sections = profile["sections"]
        has_events = profile["profile_has_events"]
    except (AttributeError, KeyError, TypeError, ValueError) as error:
        raise ReadError("DICE's page data has changed shape") from error
    events = []
    for section in sections:
        if section.get("load_more"):
            raise ReadError("DICE's venue page no longer holds the whole list")
        events += section.get("events") or []
    if has_events and not events:
        raise ReadError("DICE says there are events, but none were found")
    return events


def extract_detail(page: str) -> dict:
    for tag in BeautifulSoup(page, "html.parser").select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and "Event" in str(item.get("@type")):
                return item
    raise ReadError("a DICE event page has no event data")


def to_listing(event: dict, detail: dict, venue: Venue) -> Listing:
    starts = datetime.fromisoformat(event["dates"]["event_start_date"]).astimezone(LOCAL_TIME)
    title = " ".join(event["name"].split())
    if event.get("status") in ("cancelled", "canceled", "postponed"):
        title = f"CANCELED - {title}"
    return Listing(
        venue=venue.id,
        day=starts.date(),
        start=starts.time().replace(tzinfo=None),
        title=title,
        url=detail.get("url") or f"https://dice.fm/event/{event['id']}",
        description=detail.get("description") or "",
        lineup=tuple(p["name"].strip() for p in detail.get("performer") or [] if p.get("name")),
    )


def read(venue: Venue, web: Web, today: date) -> list[Listing]:
    listings = []
    for event in extract_events(web.get(venue.url)):
        detail = extract_detail(web.get(f"https://dice.fm/event/{event['id']}"))
        listings.append(to_listing(event, detail, venue))
    return listings
