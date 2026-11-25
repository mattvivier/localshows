from localshows.fuzzy import Candidate
from localshows.matching import match_act, overrides_from, same_song, song_title
from localshows.models import Act


class FakeSpotify:
    def __init__(self, artists, catalogs=None):
        self.artists = artists  # query -> [Candidate]
        self.catalogs = catalogs or {}  # artist id -> song titles
        self.queries = []

    def search_artists(self, name, page=0):
        self.queries.append(name)
        return self.artists.get(name, [])[page * 10 : page * 10 + 10]

    def search_tracks(self, title, artist):
        return [
            {"name": song, "artists": [{"id": artist_id}]}
            for artist_id, songs in self.catalogs.items()
            for song in songs
            if same_song(song, title)
        ]


class FakeLastFm:
    def __init__(self, songs):
        self.songs = songs

    def top_tracks(self, artist, limit=10):
        return self.songs.get(artist, [])


HITS = ["Golden Days", "No Woman", "Light Upon the Lake", "Giving Up", "Polly"]


def test_same_names_are_settled_by_songs():
    whitneys = [Candidate("a", "Whitney"), Candidate("b", "Whitney"), Candidate("c", "Whitney")]
    spotify = FakeSpotify(
        {"Whitney": whitneys},
        {"a": ["Something Else"], "b": ["No Woman - Remastered", "Golden Days (Live)"]},
    )
    result = match_act(Act("Whitney", "headliner"), spotify, FakeLastFm({"Whitney": HITS}), {})
    assert (result.status, result.artist.id) == ("matched", "b")
    assert result.votes == {"b": 2}


def test_same_names_stay_unsure_without_songs_to_go_on():
    twins = [Candidate("a", "Soul Patrol"), Candidate("b", "Soul Patrol")]
    spotify = FakeSpotify({"Soul Patrol": twins})
    result = match_act(Act("Soul Patrol", "headliner"), spotify, FakeLastFm({}), {})
    assert result.status == "unsure" and result.artist is None


def test_lone_name_match_without_any_of_its_songs_is_a_likely_namesake():
    spotify = FakeSpotify({"Whitney": [Candidate("a", "Whitney")]}, {"a": ["Other"]})
    result = match_act(Act("Whitney", "headliner"), spotify, FakeLastFm({"Whitney": HITS}), {})
    assert result.status == "unsure"


def test_small_act_matches_on_name_alone():
    spotify = FakeSpotify({"Mearth": [Candidate("a", "Mearth")]})
    result = match_act(Act("Mearth", "headliner"), spotify, FakeLastFm({}), {})
    assert (result.status, result.artist.id) == ("matched", "a")


def test_bare_name_is_searched_when_the_billed_one_finds_nothing():
    spotify = FakeSpotify({"Marc Black": [Candidate("m", "Marc Black")]})
    result = match_act(Act("The Marc Black Band", "headliner"), spotify, FakeLastFm({}), {})
    assert result.artist.id == "m"
    assert spotify.queries == ["The Marc Black Band", "Marc Black"]


def test_fallback_names_are_tried_in_order():
    spotify = FakeSpotify({"Gillian Welch": [Candidate("g", "Gillian Welch")]})
    act = Act("Gillian Welch & David Rawlings", "headliner", also=["Gillian Welch"])
    assert match_act(act, spotify, FakeLastFm({}), {}).artist.id == "g"


def test_tribute_needs_the_exact_name_and_gets_no_fallbacks():
    spotify = FakeSpotify({"Dead Man": [Candidate("d", "Dead Man")]})
    act = Act("Dead Man's Waltz", "headliner", also=["Dead Man"], tribute=True)
    assert match_act(act, spotify, FakeLastFm({}), {}).status == "none"
    assert spotify.queries == ["Dead Man's Waltz"]


def test_look_alikes_are_unsure_not_matched():
    spotify = FakeSpotify({"Lez Zeppelin": [Candidate("l", "Led Zeppelin")]})
    result = match_act(Act("Lez Zeppelin", "headliner"), spotify, FakeLastFm({}), {})
    assert result.status == "unsure" and result.artist is None


def test_overrides_pick_or_skip_without_searching():
    overrides = overrides_from({"_about": "x", "The Bob Cats": "z", "What?": None})
    spotify = FakeSpotify({})
    assert match_act(Act("Bob Cats", "opener"), spotify, None, overrides).artist.id == "z"
    assert match_act(Act("What?", "opener"), spotify, None, overrides).status == "none"
    assert spotify.queries == []


def test_song_title_ignores_version_labels():
    assert song_title("Ophelia - 2000 Remaster") == song_title("Ophelia (Live at the Fillmore)")
    assert song_title("(Intro)") == "intro"
    assert not same_song("Ophelia", "Atlantic City")
