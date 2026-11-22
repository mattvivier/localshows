"""Colony's shows page, read the way a visitor sees it, in a browser.

The calendar is drawn by a script. This reads only what the page displays and
doesn't call the calendar's data feed itself.
"""

from datetime import date, datetime

from bs4 import BeautifulSoup
from playwright.sync_api import Error as BrowserError
from playwright.sync_api import sync_playwright

from localshows.config import Venue
from localshows.models import Listing
from localshows.readers.common import clock, text_of
from localshows.web import ReadError, Web

FRAME = 'iframe[title="Events Calendar"]'
CARD = ".cl-event-card"


def extract(page: str, venue: Venue) -> list[Listing]:
    soup = BeautifulSoup(page, "html.parser")
    listings = []
    for card in soup.select(CARD):
        title = text_of(card.select_one(".cl-event-card__title"))
        shown = text_of(card.select_one(".cl-event__field--date .cl-event__field__value"))
        try:
            day = datetime.strptime(shown, "%A, %B %d, %Y").date()
        except ValueError as error:
            raise ReadError(f"can't read a Colony date: {shown!r}") from error
        link = card.select_one('a[href*="eventbrite."]')
        listings.append(
            Listing(
                venue=venue.id,
                day=day,
                start=clock(text_of(card.select_one(".cl-event__field--time"))),
                title=title,
                url=link["href"] if link else venue.url,
                description=text_of(card.select_one(".cl-event-card__description")),
            )
        )
    if not listings:
        raise ReadError("no cards found in Colony's calendar")
    return listings


def render(url: str) -> str:
    try:
        with sync_playwright() as playwright:
            # Chrome is already on Macs that have it and on GitHub's Ubuntu runners.
            browser = playwright.chromium.launch(channel="chrome", headless=True)
            try:
                page = browser.new_page(viewport={"width": 1100, "height": 1400})
                page.goto(url, timeout=60_000)
                cards = page.frame_locator(FRAME).locator(CARD)
                cards.first.wait_for(timeout=60_000)
                count, steady = 0, 0
                for _ in range(30):
                    page.mouse.wheel(0, 30_000)
                    page.wait_for_timeout(1_500)
                    now = cards.count()
                    count, steady = now, steady + 1 if now == count else 0
                    if steady >= 2:
                        # Locators see into the widget's shadow DOM; the body's inner HTML doesn't.
                        html = cards.evaluate_all("els => els.map(e => e.outerHTML)")
                        return "".join(html)
                raise ReadError("Colony's calendar never finished loading")
            finally:
                browser.close()
    except BrowserError as error:
        raise ReadError(f"Colony's page didn't render: {str(error).splitlines()[0]}") from error


def read(venue: Venue, web: Web, today: date) -> list[Listing]:
    web.check_allowed(venue.url)
    return extract(render(venue.url), venue)
