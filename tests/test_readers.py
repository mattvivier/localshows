import json
from datetime import date, time

import pytest

from localshows import listings
from localshows.config import Venue
from localshows.models import Listing
from localshows.readers import READERS, bearsville, colony, dice, partition, pearl_moon
from localshows.readers.common import clock, date_without_year
from localshows.web import ReadError

VENUE = Venue("v", "Venue", "Town", "r", "https://example.com/shows")
TODAY = date(2026, 11, 22)


def test_clock():
    assert clock("Show: 8:00 PM") == time(20)
    assert clock("12:30pm-3:00pm") == time(12, 30)
    assert clock("soon") is None


def test_year_comes_from_the_weekday():
    assert date_without_year("Monday", "Nov 30", TODAY) == date(2026, 11, 30)
    assert date_without_year("Sunday", "Jun 20", TODAY) == date(2027, 6, 20)
    with pytest.raises(ReadError):
        date_without_year("Friday", "Nov 30", TODAY)


BEARSVILLE_CARD = """
<div class="bv-event-wrapper bv-default-list">
  <span class="bv-event-weekday">Tuesday</span><span class="bv-event-monthday">Dec 8</span>
  <div class="bv-event-title"><a href="https://example.com/e">The Wood Brothers</a></div>
  <div class="bv-event-description">with Tyler Ramsey</div>
  <span class="bv-event-show">Show: 7:00 PM</span>
</div>"""


def test_bearsville_ignores_the_slideshow_copy():
    page = f'<div class="bv-events-slide">{BEARSVILLE_CARD}</div>{BEARSVILLE_CARD}'
    [found] = bearsville.extract(page, VENUE, TODAY)
    assert (found.day, found.start, found.title) == (
        date(2026, 12, 8),
        time(19),
        "The Wood Brothers",
    )
    assert found.support == "with Tyler Ramsey"


def test_pearl_moon():
    page = """<div class="event-calendar-card" data-event-start-time="9:30"
      data-event-start-date="2026-11-25T00:00:00.000+00:00">
      <h2>Molly &amp; Pep</h2><div class="event-info-text">Duo</div></div>"""
    [found] = pearl_moon.extract(page, VENUE)
    assert (found.day, found.start, found.title) == (date(2026, 11, 25), time(9, 30), "Molly & Pep")


def test_colony():
    page = """<div class="cl-event-card"><div class="cl-event-card__title">Regina Bonelli</div>
      <div class="cl-event__field--date">
        <span class="cl-event__field__value">Thursday, December 10, 2026</span></div>
      <div class="cl-event__field--time">7:00pm-10:00pm</div>
      <div class="cl-event-card__description">Blues</div>
      <a href="https://www.eventbrite.com/e/1">Buy Tickets</a></div>"""
    [found] = colony.extract(page, VENUE)
    assert (found.day, found.start, found.description) == (date(2026, 12, 10), time(19), "Blues")
    assert found.url == "https://www.eventbrite.com/e/1"


def dice_page(**section):
    profile = {"profile_has_events": True, "sections": [section]}
    data = {"props": {"pageProps": {"profile": profile}}}
    return f'<script id="__NEXT_DATA__">{json.dumps(data)}</script>'


def test_dice_refuses_a_partial_list():
    with pytest.raises(ReadError, match="whole list"):
        dice.extract_events(dice_page(load_more=True, events=[{"id": "1"}]))


def test_dice_refuses_a_false_empty():
    with pytest.raises(ReadError):
        dice.extract_events(dice_page(load_more=False, events=[]))


def test_dice_listing_uses_local_date():
    event = {
        "id": "1",
        "name": " Late  Show ",
        "dates": {"event_start_date": "2026-12-04T01:00:00+00:00"},
    }
    found = dice.to_listing(event, {"performer": [{"name": " Duchess "}]}, VENUE)
    assert (found.day, found.start, found.title) == (date(2026, 12, 3), time(20), "Late Show")
    assert found.lineup == ("Duchess",)


def wix_page(events, more=False):
    data = {"widget": {"events": {"events": events, "hasMore": more}}}
    return f'<script type="application/json">{json.dumps(data)}</script>'


def test_partition_empty_is_fine():
    assert partition.extract(wix_page([]), VENUE) == []


def test_partition_event():
    config = {"startDate": "2027-06-06T01:00:00.000Z", "timeZoneId": "America/New_York"}
    event = {"title": "The Fuze", "scheduling": {"config": config}}
    [found] = partition.extract(wix_page([event]), VENUE)
    assert (found.day, found.start) == (date(2027, 6, 5), time(21))


@pytest.mark.parametrize(
    "read",
    [
        lambda page: bearsville.extract(page, VENUE, TODAY),
        lambda page: pearl_moon.extract(page, VENUE),
        lambda page: colony.extract(page, VENUE),
        lambda page: partition.extract(page, VENUE),
        dice.extract_events,
    ],
)
def test_a_changed_page_is_an_error_not_an_empty_calendar(read):
    with pytest.raises(ReadError):
        read("<html><body>redesigned</body></html>")


def test_one_broken_venue_does_not_stop_the_rest(monkeypatch):
    def broken(venue, web, today):
        raise KeyError("gone")

    def works(venue, web, today):
        days = [date(2026, 11, 21), today, date(2027, 11, 22), date(2027, 11, 23)]
        return [Listing(venue.id, day, None, f"Band {day}", "") for day in days]

    monkeypatch.setitem(READERS, "broken", broken)
    monkeypatch.setitem(READERS, "works", works)
    venues = [Venue("a", "A", "T", "broken", ""), Venue("b", "B", "T", "works", "")]
    result = listings.collect(venues, None, TODAY)
    assert list(result.failures) == ["a"]
    assert result.counts == {"b": 2}
