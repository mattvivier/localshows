import pytest

from localshows.fuzzy import EXACT, MATCH, Candidate, best_match, mentions, similarity


@pytest.mark.parametrize(
    "billed, artist",
    [
        ("UPSTATE FAMILY BAND", "Upstate Family Band"),
        ("Larry Campbell & Teresa Williams", "Larry Campbell and Teresa Williams"),
        ("Blackmore’s Night", "Blackmore's Night"),
        ("Max Garcìa Conover", "Max García Conover"),
        ("Moe.", "moe."),
        ("The Champagne Poneys", "Champagne Poneys"),
        ("Bob Cats", "Bobcats"),
        ("Medeski, Martin, Metzger, Cline", "Medeski, Martin, Metzger & Cline"),
        ("Five O'Clock Somewhere", "5 O’Clock Somewhere"),
        ("The Marc Black Band", "Marc Black"),
        ("Alexis P. Suter Band", "Alexis P. Suter"),
        ("Maria Mazotta", "Maria Mazzotta"),
        ("Noah Gunderson", "Noah Gundersen"),
        ("Ominous Seapdos", "Ominous Seapods"),
    ],
)
def test_same_act(billed, artist):
    assert similarity(billed, artist) >= MATCH
    assert similarity(artist, billed) >= MATCH


@pytest.mark.parametrize(
    "billed, artist",
    [
        ("Lez Zeppelin", "Led Zeppelin"),
        ("The Pink Floyd Project", "Pink Floyd"),
        ("Pink Froyd", "Pink Floyd"),
        ("Sons Of Cream", "Cream"),
        ("Soul Patrol", "Soul Purpose"),
        ("Molly & Pep", "Molly"),
        ("The Band", "Band of Horses"),
        ("Gary Smith", "Gary Smyth"),
        ("Bill Evans Trio", "Bill Evans Quartet"),
        ("Jazz Band", "Jazz"),
        ("Naked", "Naked Eyes"),
        ("Tree of Life Quartet", "Tree of Life"),
        ("9 FEET DOWN", "6 Feet Down"),
        ("Hudson Valley Flyers", "Hudson Valley Boys"),
    ],
)
def test_different_acts(billed, artist):
    assert similarity(billed, artist) < MATCH
    assert similarity(artist, billed) < MATCH


def test_exact_beats_fuzzy():
    found = best_match(
        ["The Marc Black Band"],
        [Candidate("1", "Marc Black"), Candidate("2", "Marc Black Band")],
    )
    assert (found.status, found.candidates[0].id, found.score) == ("matched", "2", EXACT)


def test_names_are_tried_in_order():
    found = best_match(
        ["Gary Lucas & Gods and Monsters", "Gary Lucas"], [Candidate("1", "Gary Lucas")]
    )
    assert (found.status, found.candidates[0].id) == ("matched", "1")


def test_two_artists_with_one_name_are_unsure():
    found = best_match(["Naked"], [Candidate("1", "Naked"), Candidate("2", "NAKED")])
    assert found.status == "unsure"


def test_the_same_artist_twice_is_not_ambiguous():
    found = best_match(["moe."], [Candidate("1", "moe."), Candidate("1", "moe.")])
    assert found.status == "matched"


def test_near_miss_is_unsure_and_never_picked():
    assert best_match(["Lez Zeppelin"], [Candidate("1", "Led Zeppelin")]).status == "unsure"


def test_tributes_need_an_exact_name():
    close = [Candidate("1", "Muscle Shoal")]
    assert best_match(["Muscle Shoals"], close).status == "matched"
    assert best_match(["Muscle Shoals"], close, exact_only=True).status == "unsure"


def test_punctuation_as_billed_breaks_a_tie():
    found = best_match(
        ["Moe."], [Candidate("1", "MoE"), Candidate("2", "moe."), Candidate("3", "M.O.E.")]
    )
    assert (found.status, found.candidates[0].id) == ("matched", "2")


def test_tribute_does_not_match_a_respaced_name():
    found = best_match(["The Bob Cats"], [Candidate("1", "Bobcats")], exact_only=True)
    assert found.status == "unsure"


def test_nothing_alike():
    assert best_match(["DakhaBrakha"], [Candidate("1", "Wilco")]).status == "none"


def test_mentions_allows_a_typo():
    assert mentions("an evening with Maria Mazotta and band", "Maria Mazzotta")
    assert not mentions("the music of Led Zeppelin", "Lez Zeppelin")
