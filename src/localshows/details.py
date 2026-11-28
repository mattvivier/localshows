"""Fetch each show's own page for its write-up, which helps tell namesakes apart.

This is extra: a page that fails or has changed leaves the write-up empty and never
fails the venue, whose calendar has already been read.
"""

import dataclasses

from bs4 import BeautifulSoup

from localshows.models import Listing
from localshows.readers.common import text_of
from localshows.web import ReadError, Web

# Where the write-up sits, for readers whose calendar doesn't include it. Only that
# block, so that "more shows" strips naming other bands don't count as evidence.
WRITE_UP = {
    "bearsville": ".et_pb_post_content",
    "colony": "[data-testid=section-wrapper-overview]",
}
LIMIT = 6000


def write_up(html: str, selector: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return " ".join(text_of(node) for node in soup.select(selector))[:LIMIT]


def add_write_ups(listings: list[Listing], reader: str, web: Web) -> tuple[list[Listing], int]:
    """Return the listings with page_text filled in, and how many pages had none."""
    selector = WRITE_UP.get(reader)
    if not selector:
        return listings, 0
    texts: dict[str, str] = {}
    for url in dict.fromkeys(item.url for item in listings if item.url):
        try:
            texts[url] = write_up(web.get(url), selector)
        except ReadError:
            texts[url] = ""
    missing = sum(1 for text in texts.values() if not text)
    return [
        dataclasses.replace(item, page_text=texts.get(item.url, "")) for item in listings
    ], missing
