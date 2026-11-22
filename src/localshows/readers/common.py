"""Helpers the readers share."""

import re
from datetime import date, datetime, time

from bs4 import Tag

from localshows.web import ReadError


def text_of(node: Tag | None) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip() if node else ""


def clock(text: str) -> time | None:
    """The first "7:00 PM" or "7:00pm" in text."""
    found = re.search(r"(\d{1,2}):(\d\d)\s*([ap])m", text, re.I)
    if not found:
        return None
    hour = int(found[1]) % 12 + (12 if found[3].lower() == "p" else 0)
    return time(hour, int(found[2]))


def date_without_year(weekday: str, month_day: str, today: date) -> date:
    """Resolve "Wednesday", "Jan 20" to the nearest such date that isn't long past."""
    options = []
    for year in (today.year - 1, today.year, today.year + 1, today.year + 2):
        try:
            day = datetime.strptime(f"{month_day} {year}", "%b %d %Y").date()
        except ValueError:
            continue
        if day.strftime("%A") == weekday and -60 <= (day - today).days <= 550:
            options.append(day)
    if not options:
        raise ReadError(f"can't place the date {weekday} {month_day}")
    return min(options, key=lambda day: abs((day - today).days))
