from datetime import date

from localshows.fuzzy import Candidate
from localshows.matching import Context, fits_room, match_act, overrides_from, song_title
from localshows.models import Act
from localshows.spotify import Catalog, release_day

TODAY = date(2026, 11, 28)
SMALL_ROOM = Context(rooms=[(150_000, 0)])


class FakeSpotify:
    def __init__(self, artists, followers=None, catalogs=None):
        self.artists = artists  # query -> [Candidate]
        self.followers = followers or {}
        self.catalogs = catalogs or {}
        self.queries, self.looked_up = [], []

    def search_artists(self, name, page=0):
        self.queries.append(name)
        return self.artists.get(name, [])[page * 10 : page * 10 + 10]

    def catalog(self, artist_id):
        self.looked_up.append(artist_id)
        return self.catalogs.get(artist_id, Catalog())


def three(name):
    return [Candidate(x, name) for x in "abc"]


def test_write_up_naming_a_member_settles_same_names():
    spotify = FakeSpotify(
        {"Duchess": three("Duchess")},
        catalogs={
            "a": Catalog({"Something"}, {"Nobody Known"}),
            "b": Catalog({"Other Song Title"}, {"Jane Doe Smith"}),
        },
    )
    context = Context("Duchess features Jane Doe Smith on guitar and vocals", [(150_000, 0)])
    result = match_act(Act("Duchess", "headliner"), context, spotify, {}, TODAY)
    assert (result.status, result.artist.id) == ("matched", "b")
    assert result.clues["b"].people == ["jane doe smith"]


def test_write_up_naming_an_album_settles_same_names():
    spotify = FakeSpotify(
        {"Whitney": three("Whitney")},
        catalogs={"c": Catalog({"Light Upon the Lake (Deluxe)"})},
    )
    context = Context("Touring behind Light Upon the Lake.")
    result = match_act(Act("Whitney", "headliner"), context, spotify, {}, TODAY)
    assert result.artist.id == "c"


def test_a_shared_cover_or_a_self_title_tells_nothing():
    shared = Catalog({"Silent Night", "Midnight Rambler Blues", "Duchess Live"})
    spotify = FakeSpotify({"Duchess": three("Duchess")[:2]}, catalogs={"a": shared, "b": shared})
    context = Context("Duchess play Midnight Rambler Blues and Silent Night: Duchess Live!")
    result = match_act(Act("Duchess", "headliner"), context, spotify, {}, TODAY)
    assert result.status == "unsure"


def test_only_one_that_fits_the_room():
    spotify = FakeSpotify({"Whitney": three("Whitney")}, {"a": 2_000_000, "b": 900, "c": 5_000_000})
    result = match_act(Act("Whitney", "headliner"), SMALL_ROOM, spotify, {}, TODAY)
    assert (result.status, result.artist.id) == ("matched", "b")


def test_still_releasing_breaks_an_even_tie():
    spotify = FakeSpotify(
        {"Soul Patrol": three("Soul Patrol")[:2]},
        catalogs={"a": Catalog(latest=date(2009, 1, 1)), "b": Catalog(latest=date(2025, 6, 1))},
    )
    result = match_act(Act("Soul Patrol", "headliner"), Context(), spotify, {}, TODAY)
    assert result.artist.id == "b"


def test_same_names_with_nothing_to_go_on_stay_unsure():
    spotify = FakeSpotify({"Soul Patrol": three("Soul Patrol")})
    result = match_act(Act("Soul Patrol", "headliner"), Context(), spotify, {}, TODAY)
    assert result.status == "unsure" and result.artist is None


def test_lone_name_match_that_fits_needs_no_catalog():
    spotify = FakeSpotify({"Mearth": [Candidate("a", "Mearth")]}, {"a": 300})
    result = match_act(Act("Mearth", "headliner"), SMALL_ROOM, spotify, {}, TODAY)
    assert (result.status, result.artist.id) == ("matched", "a")
    assert spotify.looked_up == []


def test_lone_name_match_far_too_big_is_a_likely_namesake():
    spotify = FakeSpotify({"Whitney": [Candidate("a", "Whitney")]}, {"a": 4_000_000})
    result = match_act(Act("Whitney", "headliner"), SMALL_ROOM, spotify, {}, TODAY)
    assert result.status == "unsure"


def test_write_up_evidence_outweighs_the_room_guess():
    spotify = FakeSpotify(
        {"Whitney": [Candidate("a", "Whitney")]},
        {"a": 4_000_000},
        {"a": Catalog({"Golden Days"})},
    )
    context = Context("Whitney play Golden Days", [(150_000, 0)])
    result = match_act(Act("Whitney", "headliner"), context, spotify, {}, TODAY)
    assert result.status == "matched"


def test_headliner_floor_and_missing_counts():
    assert fits_room(500, [(3_000_000, 1_000)]) is False
    assert fits_room(500, [(3_000_000, 1_000), (150_000, 0)]) is True
    assert fits_room(None, [(150_000, 0)]) is None


def test_bare_name_is_searched_when_the_billed_one_finds_nothing():
    spotify = FakeSpotify({"Marc Black": [Candidate("m", "Marc Black")]})
    result = match_act(Act("The Marc Black Band", "headliner"), Context(), spotify, {}, TODAY)
    assert result.artist.id == "m"
    assert spotify.queries == ["The Marc Black Band", "Marc Black"]


def test_fallback_names_are_tried_in_order():
    spotify = FakeSpotify({"Gillian Welch": [Candidate("g", "Gillian Welch")]})
    act = Act("Gillian Welch & David Rawlings", "headliner", also=["Gillian Welch"])
    assert match_act(act, Context(), spotify, {}, TODAY).artist.id == "g"


def test_tribute_needs_the_exact_name_and_gets_no_fallbacks():
    spotify = FakeSpotify({"Dead Man": [Candidate("d", "Dead Man")]})
    act = Act("Dead Man's Waltz", "headliner", also=["Dead Man"], tribute=True)
    assert match_act(act, Context(), spotify, {}, TODAY).status == "none"
    assert spotify.queries == ["Dead Man's Waltz"]


def test_look_alikes_are_unsure_not_matched():
    spotify = FakeSpotify({"Lez Zeppelin": [Candidate("l", "Led Zeppelin")]})
    result = match_act(Act("Lez Zeppelin", "headliner"), Context(), spotify, {}, TODAY)
    assert result.status == "unsure" and result.artist is None


def test_overrides_pick_or_skip_without_searching():
    overrides = overrides_from({"_about": "x", "The Bob Cats": "z", "What?": None})
    spotify = FakeSpotify({})
    assert (
        match_act(Act("Bob Cats", "opener"), Context(), spotify, overrides, TODAY).artist.id == "z"
    )
    assert match_act(Act("What?", "opener"), Context(), spotify, overrides, TODAY).status == "none"
    assert spotify.queries == []


def test_titles_and_dates():
    assert song_title("Ophelia - 2000 Remaster") == song_title("Ophelia (Live at the Fillmore)")
    assert song_title("(Intro)") == "intro"
    assert release_day("2019") == date(2019, 1, 1)
    assert release_day("2019-05-03") == date(2019, 5, 1)
    assert release_day("") is None
