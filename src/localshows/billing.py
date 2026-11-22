"""Work out who is playing from the way a venue worded its listing.

Venues bury the act in slogans ("Get Ready to Groove with Soul Patrol!"), series names
("Local Waves: Play Time") and tributes ("A John Prine Christmas!"). These rules are
general patterns, not per-show fixes. An honored artist is never billed as the act.
"""

import re
import unicodedata
from collections import Counter, defaultdict

from localshows import fuzzy
from localshows.models import Act, Listing, Show

_DAYS = r"(?:sun|mon|tues|wednes|thurs|fri|satur)day"

_NOT_A_SHOW = {
    "open mic": r"\bopen[ -]mi(?:c|ke)\b",
    "karaoke": r"\bkaraoke\b",
    "jam session": r"\b(?:pro|open|community|john st\.?|blues) jam\b",
    "multi-day pass": r"\b(?:\d|two|three|weekend)[ -]?(?:day|night)? pass\b",
    "not a concert": r"\b(?:trivia|burlesque|comedy night|bingo|private event)\b",
}
_CANCELED = re.compile(r"^\W*(?:cancel+ed|postponed)\b", re.I)

# Words that mark a phrase as the name of an event instead of an act.
_EVENT = re.compile(
    rf"""\b(?:
      brunch | party | christmas | holiday | birthday | bash | spectacular | revival
    | celebration | favou?rites | festival | fundraiser | benefit | nye | new\ year
    | thanksgiving | halloween | dinner\ show | album\ release | tour | anniversary
    | get\ ready | ring\ in | all\ aboard | kick\ off
    | last\ {_DAYS} | {_DAYS}\ night
    | (?:punk|jazz|blues|dance|metal|folk|country|latin|reggae|funk|soul|game)\ night
    | night\ (?:in|of) | evening\ (?:of|with)
    )\b""",
    re.I | re.X,
)
_SERIES = re.compile(r"^(?:songs (?:from|of)\b|an? evening\b|live at\b)", re.I)
_EVENING_WITH = re.compile(
    r"^an? (?:[\w-]+ )?(?:evening|weekend|night) (?:with|w/)\s*(?:public radio's\s+)?", re.I
)
_PRESENTED_BY = re.compile(r"^.+?\s+[-–—]\s+presented by\s+(.+)$", re.I)
_PRESENTS = re.compile(r"^(.+?)\s+presents?:\s*(.+)$", re.I)
_PROMOTER = re.compile(
    r"\b(?:relix|productions|promotions|live|colony|records|house)\b|house$", re.I
)
_WITH = re.compile(r"\s+w/\s*|\s+with\s+", re.I)
_FEATURING = re.compile(r"\s+(?:ft\.?|feat\.?|featuring)\s+", re.I)
_SUPPORT = re.compile(r"^(?:with\s+|w/\s*|featuring\s+|ft\.?\s+)(.+)$", re.I)
_GUEST = re.compile(
    r"^(?:very )?(?:special )?guests?(?: (?:vocalist|guitarist|drummer|dj))?:?\s+", re.I
)
_TRAILING_EVENT = re.compile(
    rf"\s+(?:{_DAYS}\s+)?(?:brunch|dinner show|album release(?: show| party)?)$", re.I
)
_SUBTITLE = re.compile(
    r"\s+(?:the (?:very )?(?:first|last|final|farewell) shows?"
    r"|(?:world|farewell|reunion|solo|acoustic) tour|acoustic|unplugged)$",
    re.I,
)
_PLAYS = re.compile(r"^(\S+\s+\S.*?)\s+(?:plays?|performs?)\s+\S", re.I)
_SHOUTED_NAME = re.compile(r"^([A-Z]{2,}(?: [A-Z]{2,})+) (?:[A-Z][a-z]+ ?){3,}$")
_POSSESSIVE = re.compile(r"^(.+?)'s\s|^(.+?s)'\s", re.I)
_SEASONAL = re.compile(r"^an? (.+?) (?:christmas|holiday)$", re.I)
_TRIBUTE = re.compile(
    r"(?i:\btribute\b|\bsalute to\b|\bmusic of\b|\bexperience you can\b)"
    r"|\b[A-Z]\w+ [A-Z]\w+ experience\b|\b[Cc]elebration of [A-Z]"
)
_CONCERT_WITH = re.compile(r"\bconcert\b[^.*]*?\bwith\b[^.*]*\*\*([^*]+)\*\*", re.I)


def _clean(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'")
    text = "".join(c for c in text if unicodedata.category(c) not in ("So", "Cf"))
    text = re.sub(r"\*[^*]+\*", " ", text)
    text = re.sub(r"\([^)]*(?:tour|anniversary|night \d)[^)]*\)", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"[\s!:–—-]+$", "", text)


def _names(text: str, *, split_and: bool) -> list[str]:
    """Split a list of acts. Band names contain "and", so only split when it's clearly a list."""
    if "," in text:
        parts = re.split(r",\s*(?:&\s*|and\s+)?|\s+&\s+", text)
    elif split_and:
        parts = re.split(r"\s+and\s+(?!(?:the|his|her|their)\b)", text, flags=re.I)
        people = re.split(r"\s+&\s+(?!the\b)", text, flags=re.I)
        if len(people) > 1 and all(len(person.split()) == 2 for person in people):
            parts = people
    else:
        parts = [text]
    parts = [re.split(r"\s+[-–—]\s+", part)[0] for part in parts]  # "- Jerry's Birthday"
    return [part.strip(" !") for part in parts if part.strip(" !")]


def _pick_side_of_colon(left: str, right: str, description: str, series: set[str]) -> str:
    if fuzzy.normalize(left) in series or _SERIES.search(left):
        return right
    if _EVENT.search(right):
        return left
    if fuzzy.mentions(description, right) and not fuzzy.mentions(description, left):
        return right
    return left


def _lead_acts(text: str, description: str, series: set[str]) -> list[str]:
    """The act or acts named before any "with"; empty if it only names the event."""
    if ": " in text:
        left, right = text.split(": ", 1)
        text = _pick_side_of_colon(left, right, description, series)
    text = re.split(r"\s+[-–—|]\s+", text)[0].strip(" !")
    if " / " in text:
        left, right = text.split(" / ", 1)
        if _EVENT.search(right):
            text = left
    stripped = _TRAILING_EVENT.sub("", text).strip(" !")
    if re.fullmatch(rf"{_DAYS}|an?|the", stripped, re.I):
        return []  # "Sunday Brunch" is all event
    text = _SUBTITLE.sub("", stripped)
    if found := _PLAYS.match(text):
        text = found[1]
    if found := _SHOUTED_NAME.match(text):
        text = found[1]
    if not _EVENT.search(text):
        return [part for part in re.split(r"\s+[+x]\s+", text) if part]
    # "A Bean Tones Christmas" is the Bean Tones; "A John Prine Christmas" is not John Prine.
    # The difference is whether the description has them doing the performing.
    if found := _SEASONAL.match(text):
        name = re.escape(found[1])
        if re.search(rf"\b{name} (?:are|is|brings?|returns?|performs?)\b", description, re.I):
            return [found[1]]
        return []
    if found := _POSSESSIVE.match(text):
        owner = found[1] or found[2]
        if not _EVENT.search(owner):
            return [owner]
    return []


def _other_names(name: str) -> list[str]:
    """Fallbacks: the bandleader in "Gary Lucas & Gods and Monsters"."""
    also = []
    if "," in name:
        # "Tim O'Brien, Sam Grisman & ..." can fall back on each person in it.
        also += [part for part in _names(name, split_and=True) if len(part.split()) >= 2]
        return also
    parts = re.split(r"\s+(?:&|and)\s+", name, flags=re.I)
    if len(parts) > 1:
        people = all(len(part.split()) == 2 for part in parts)
        if people:
            also += parts
        elif len(parts[0].split()) >= 2:
            also.append(parts[0])
    if (found := _POSSESSIVE.match(name)) and len((found[1] or found[2]).split()) >= 2:
        also.append(found[1] or found[2])
    return also


def parse(listing: Listing, series: set[str] = frozenset()) -> Show:
    show = Show(listing)
    if _CANCELED.search(listing.title):
        show.skipped = "canceled or postponed"
        return show
    for reason, pattern in _NOT_A_SHOW.items():
        if re.search(pattern, listing.title, re.I):
            show.skipped = reason
            return show

    title, description = _clean(listing.title), listing.description.replace("’", "'")
    if found := _PRESENTED_BY.match(title):
        title = found[1]
    elif found := _PRESENTS.match(title):
        title = found[2] if _PROMOTER.search(found[1]) else found[1]
    title = _EVENING_WITH.sub("", title)

    main, *after_with = _WITH.split(title, maxsplit=1)
    main, *featured = _FEATURING.split(main, maxsplit=1)
    openers: list[str] = []
    guests: list[str] = []
    for text in featured:
        guests += _names(text, split_and=True)

    leads = _lead_acts(main, description, series)

    billed_support = [(text, bool(leads)) for text in after_with]
    if found := _SUPPORT.match(_clean(listing.support)):
        billed_support.append((found[1], True))
    for text, split_and in billed_support:
        text, *featured = _FEATURING.split(text, maxsplit=1)
        for extra in featured:
            guests += _names(extra, split_and=True)
        if _GUEST.match(text):
            guests += _names(_GUEST.sub("", text), split_and=True)
        else:
            openers += _names(text, split_and=split_and)

    # "Molly Venter of Red Molly" is Molly Venter.
    guests = [re.sub(r"^(\S+ \S+) of [A-Z].*$", r"\1", guest) for guest in guests]

    if listing.lineup:
        # The ticketing site's lineup wins, worded as the title has it when that's fuller.
        billed = []
        for performer in listing.lineup:
            titled = (
                n
                for n in [*leads, *title.split(": ")]
                if fuzzy.similarity(n, performer) >= fuzzy.MATCH
            )
            billed.append(next(titled, performer.strip()))
        openers = billed[1:] + [
            name for name in openers if all(fuzzy.similarity(name, b) < fuzzy.MATCH for b in billed)
        ]
        leads = billed[:1]
    elif found := _CONCERT_WITH.search(description):
        leads = [found[1].strip()]

    # Billing order decides when nothing says who headlines.
    if leads:
        openers = leads[1:] + openers
        leads = leads[:1]
    elif guests and _featured_first(title):
        # "Christmas ft. A, B & C": with no act before them, they share the bill.
        leads, openers, guests = guests[:1], guests[1:] + openers, []
    elif openers:
        leads, openers = openers[:1], openers[1:]
    elif guests:
        leads, guests = guests[:1], guests[1:]

    tribute = bool(_TRIBUTE.search(f"{listing.title} {listing.support} {description[:250]}"))
    for role, names in (("headliner", leads), ("opener", openers), ("guest", guests)):
        for name in names:
            is_tribute = tribute and role == "headliner"
            # A tribute gets no fallbacks: "Dead Man's Waltz" mustn't become "Dead Man".
            also = [] if is_tribute else _other_names(name)
            act = Act(name, role, also, is_tribute)
            for performer in listing.lineup:
                if name != performer.strip() and fuzzy.mentions(name, performer):
                    act.also.insert(0, performer.strip())
            show.acts.append(act)
    return show


def _featured_first(title: str) -> bool:
    featured, joined = _FEATURING.search(title), _WITH.search(title)
    return bool(featured) and (not joined or featured.start() < joined.start())


def _series_names(listings: list[Listing]) -> set[str]:
    """A label before a colon that recurs with different acts after it is a series."""
    following = defaultdict(set)
    for listing in listings:
        if ": " in listing.title:
            left, right = listing.title.split(": ", 1)
            following[(listing.venue, fuzzy.normalize(left))].add(fuzzy.normalize(right))
    return {left for (_, left), rights in following.items() if len(rights) > 1}


def _dedupe(listings: list[Listing]) -> list[Listing]:
    """Drop a show listed twice. Early and late sets have different times, so they stay."""
    kept: list[Listing] = []
    for listing in listings:
        if not any(
            (other.venue, other.day, other.start) == (listing.venue, listing.day, listing.start)
            and fuzzy.similarity(other.title, listing.title) >= fuzzy.MATCH
            for other in kept
        ):
            kept.append(listing)
    return kept


def _reconcile(shows: list[Show]) -> None:
    """Give an act one name however each listing spells it."""
    acts = [act for show in shows for act in show.acts]
    names = Counter(act.name for act in acts)

    # "...Brunch with Jay Collins" whose blurb says "Jay Collins' Gravy Train" is that band.
    for show in shows:
        for act in show.acts:
            for full in names:
                if (
                    act.name != full
                    and act.name in _other_names(full)
                    and _POSSESSIVE.match(full)
                    and fuzzy.mentions(show.listing.description, full)
                ):
                    act.also.insert(0, act.name)
                    act.name = full
                    break

    # Prefer the commonest spelling, then one that isn't shouting.
    chosen: list[str] = []
    for name in sorted(names, key=lambda n: (-names[n], n.isupper(), n)):
        if all(fuzzy.similarity(name, other) < fuzzy.MATCH for other in chosen):
            chosen.append(name)
    for act in acts:
        for name in chosen:
            if act.name != name and fuzzy.similarity(act.name, name) >= fuzzy.MATCH:
                act.also.insert(0, act.name)
                act.name = name
                break


def parse_all(listings: list[Listing]) -> list[Show]:
    listings = _dedupe(listings)
    series = _series_names(listings)
    shows = [parse(listing, series) for listing in listings]
    _reconcile(shows)
    return sorted(
        shows, key=lambda s: (s.listing.day, s.listing.start is None, str(s.listing.start))
    )
