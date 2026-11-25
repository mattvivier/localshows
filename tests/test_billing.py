"""Real titles from the venues' sites, November 2026."""

from datetime import date, time

import pytest

from localshows.billing import parse, parse_all
from localshows.models import Listing


def listing(title, description="", support="", lineup=(), day=1, venue="v", start=time(19)):
    when = date(2026, 12, day)
    return Listing(venue, when, start, title, "", description, support, tuple(lineup))


def billed(show):
    marks = {"headliner": "", "opener": "+", "guest": "ft "}
    return [marks[act.role] + act.name for act in show.acts]


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Mearth w/ El Front and Dirt Surfers", ["Mearth", "+El Front", "+Dirt Surfers"]),
        (
            "Punk Night w/ NCM, Modern Natives, & King In Yellow",
            ["NCM", "+Modern Natives", "+King In Yellow"],
        ),
        (
            "Seth Walker x Goodnight Moonshine ft. Molly Venter of Red Molly",
            ["Seth Walker", "+Goodnight Moonshine", "ft Molly Venter"],
        ),
        (
            "The Shambles ft Jay Collins and Martee Lebow - Jerry’s 75th Birthday show",
            ["The Shambles", "ft Jay Collins", "ft Martee Lebow"],
        ),
        (
            "Rick Danko Birthday ft. Prof. Louie & The Crowmatix w/ The Woodstock Horns",
            ["Prof. Louie & The Crowmatix", "+The Woodstock Horns"],
        ),
        (
            "Cosmic Charlie Brown Christmas ft. Jason Crosby, Johnny Kimock, & Kevin Reilly",
            ["Jason Crosby", "+Johnny Kimock", "+Kevin Reilly"],
        ),
        (
            "The Smithereens w/ guest vocalist Marshall Crenshaw",
            ["The Smithereens", "ft Marshall Crenshaw"],
        ),
        ("First Day Back + Rainer Maria", ["First Day Back", "+Rainer Maria"]),
        ("Blackmore’s Night with Wizards Consort", ["Blackmore's Night", "+Wizards Consort"]),
        ("The Last Waltz - Presented by Stagefright", ["Stagefright"]),
        ("An Intimate Evening with Moe.", ["Moe."]),
        ("A Goovy Evening with UPSTATE FAMILY BAND!", ["UPSTATE FAMILY BAND"]),
        ("Get Ready to Groove with Soul Patrol!", ["Soul Patrol"]),
        ("Sunday Brunch w/ Tillson Ensemble", ["Tillson Ensemble"]),
        ("Brad Cole & Bossa Blue Dinner Show", ["Brad Cole & Bossa Blue"]),
        (
            "NYE PARTY with Chris Wells and The Silver Spaceship",
            ["Chris Wells and The Silver Spaceship"],
        ),
        ("'Dead Last Wednesday' with Gratefully Yours", ["Gratefully Yours"]),
        ("DJ Magic Juan: Thanksgiving Eve Party!", ["DJ Magic Juan"]),
        ("Yukon Cornelius' Holiday Spectacular!", ["Yukon Cornelius"]),
        ("Robert Burke Warren's Bowie Birthday Bash '27", ["Robert Burke Warren"]),
        (
            "Bruce Katz and Joel Harrison Present: A Night in New Orleans",
            ["Bruce Katz and Joel Harrison"],
        ),
        ("Mihali presents: Mihalidaze", ["Mihali"]),
        (
            "Gillian Welch and David Rawlings Play Grateful Dead Acoustic Reckoning",
            ["Gillian Welch and David Rawlings"],
        ),
        ("CLAUDIO SANCHEZ The Very First Shows", ["CLAUDIO SANCHEZ"]),
        ("Big Shrimp *Album Release*", ["Big Shrimp"]),
        ("The Arcadian Wild - Make It Out Alive Tour", ["The Arcadian Wild"]),
        ("Todd Rundgren: DAMNED IF I DO TOUR", ["Todd Rundgren"]),
        ("Whitney: Light Upon The Lake (10th Anniversary Tour)", ["Whitney"]),
        ("Foy Vance World Tour | 2026 & 2027", ["Foy Vance"]),
        ("An Intimate Weekend w/ Laith Al-Saadi (Friday, Night 1)", ["Laith Al-Saadi"]),
        ("An Evening With Maya Hawke / The Maitreya Corso Tour", ["Maya Hawke"]),
        ("Soul Asylum Acoustic", ["Soul Asylum"]),
    ],
)
def test_titles(title, expected):
    assert billed(parse(listing(title))) == expected


@pytest.mark.parametrize(
    "title",
    [
        "THE WORLD FAMOUS COLONY OPEN MIC!",
        "Sonny Rock's Pro Jam #55",
        "moe. 2-Day Pass",
        "Monday Karaoke",
        "Strangehouse Presents: ✨ Seasons Shimmies: A Holiday Burlesque & Cabaret",
        "CANCELED - Lola Kirke",
        "CANCELLED: An Evening with Paul Cauthen",
    ],
)
def test_not_a_show(title):
    show = parse(listing(title))
    assert show.skipped and not show.acts


def test_honored_artist_is_not_the_act():
    show = parse(listing("A John Prine Christmas!", "the soulful tunes of John Prine at Colony"))
    assert not show.acts


def test_seasonal_show_by_the_act_itself():
    show = parse(listing("A Bean Tones Christmas", "The Bean Tones are redefining vocal jazz"))
    assert billed(show) == ["Bean Tones"]


@pytest.mark.parametrize(
    "title, description",
    [
        ("Muscle Shoals: The Music Of The Allman Brothers Band & Friends", ""),
        ("Harvest And Rust: A Tribute To Neil Young", ""),
        ("The Bob Cats", "All-Star Salute to Dylan"),
        ("Lez Zeppelin: The Song Remains The Same", "their authentic Led Zeppelin experience"),
    ],
)
def test_tributes_are_flagged(title, description):
    assert parse(listing(title, description)).headliner.tribute


def test_tribute_has_no_fallback_names():
    show = parse(listing("Dead Man's Waltz", "a tribute to the music of The Grateful Dead"))
    assert show.headliner.also == []


def test_two_guests_joined_by_an_ampersand():
    show = parse(listing("Midnight Ramble ft. Chaney Sims & Jackson Speller"))
    assert [act.name for act in show.support] == ["Chaney Sims", "Jackson Speller"]


def test_support_line():
    show = parse(listing("The Wood Brothers", support="with Tyler Ramsey"))
    assert billed(show) == ["The Wood Brothers", "+Tyler Ramsey"]
    assert billed(parse(listing("Martin Sexton", support="Live Wide Open Tour"))) == [
        "Martin Sexton"
    ]


def test_lineup_wins_and_keeps_the_fuller_billed_name():
    show = parse(listing("The Blues: Alexis P. Suter Band", lineup=["Alexis P. Suter"]))
    assert billed(show) == ["Alexis P. Suter Band"]
    assert "Alexis P. Suter" in show.headliner.also


def test_concert_named_in_description():
    show = parse(
        listing(
            "An Evening with Public Radio's Afropop Worldwide: Film, Music, Food",
            "a film followed by a concert at The Local with the amazing **Mandingo Ambassadors**",
        )
    )
    assert billed(show) == ["Mandingo Ambassadors"]


def test_recurring_series_label_is_not_the_act():
    shows = parse_all(
        [
            listing("Local Waves: Play Time", day=9),
            listing("Local Waves: The Champagne Poneys", day=13),
        ]
    )
    assert [billed(show) for show in shows] == [["Play Time"], ["The Champagne Poneys"]]


def test_one_act_spelled_two_ways_gets_one_name():
    shows = parse_all(
        [
            listing("A Goovy Evening with UPSTATE FAMILY BAND!", day=1),
            listing("Ring in the New Year with Upstate Family Band!", day=31),
        ]
    )
    assert [show.headliner.name for show in shows] == ["Upstate Family Band"] * 2


def test_bandleader_becomes_the_band_when_the_blurb_says_so():
    shows = parse_all(
        [
            listing("Jay Collins’ GRAVY TRAIN Sunday Brunch !", day=1),
            listing(
                "All Aboard the Gravy Train! Sunday Brunch with Jay Collins!",
                "swing with Jay Collins' Gravy Train",
                day=27,
            ),
        ]
    )
    assert [show.headliner.name for show in shows] == ["Jay Collins' GRAVY TRAIN"] * 2


def test_duplicate_listing_is_dropped_but_second_set_stays():
    shows = parse_all(
        [
            listing("The Wood Brothers"),
            listing("Wood Brothers"),
            listing("The Wood Brothers", start=time(21)),
        ]
    )
    assert len(shows) == 2


def test_billing_falls_back_on_each_person():
    also = parse(listing("Larry Campbell & Teresa Williams")).headliner.also
    assert also == ["Larry Campbell", "Teresa Williams"]


def test_members_of_another_band_is_not_an_act():
    show = parse(
        listing("The Weight Band", support="ft. former members of The Band & Levon Helm Band")
    )
    assert billed(show) == ["The Weight Band"]
