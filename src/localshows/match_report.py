"""Match every billed act, and write the details for a person to read.

Spotify's names, links and numbers go only to the gitignored report file; the console
gets counts and the venues' own act names.
"""

from collections import Counter
from datetime import date
from pathlib import Path

from localshows import state
from localshows.config import Venue
from localshows.fuzzy import normalize
from localshows.matching import ArtistMatch, Context, match_act, overrides_from
from localshows.models import Act, Show


def contexts(shows: list[Show], venues: list[Venue]) -> dict[str, tuple[Act, Show, Context]]:
    """Each act once, with what every one of its shows says and how big those rooms are."""
    rooms = {venue.id: venue for venue in venues}
    found: dict[str, tuple[Act, Show, Context]] = {}
    for show in sorted(shows, key=lambda s: (s.listing.day, s.listing.venue)):
        listing = show.listing
        text = " ".join(
            [
                listing.title,
                listing.support,
                *listing.lineup,
                listing.description,
                listing.page_text,
            ]
        )
        venue = rooms.get(listing.venue)
        for act in show.acts:
            entry = found.setdefault(normalize(act.name), (act, show, Context()))
            context = entry[2]
            if text not in context.text:
                context.text = f"{context.text} {text}".strip()
            if venue:
                floor = venue.headliner_min_followers if act.role == "headliner" else 0
                context.rooms.append((venue.followers_max, floor))
    return found


def run(
    shows: list[Show], venues: list[Venue], spotify, root: Path, today: date
) -> tuple[list[ArtistMatch], Path]:
    overrides = overrides_from(state.load(root / "config" / "overrides.json", {}))
    results, lines = [], []
    for act, show, context in contexts(shows, venues).values():
        result = match_act(act, context, spotify, overrides, today)
        results.append(result)
        lines += _describe(result, act, show)
    path = root / "local" / "matches.txt"
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results, path


def _describe(result: ArtistMatch, act: Act, show: Show) -> list[str]:
    listing = show.listing
    head = f"[{result.status.upper()}] {act.name}  ({listing.venue} {listing.day}, {act.role})"
    lines = [head, f"    how: {result.how}"]
    if result.name_used != act.name and result.name_used:
        lines.append(f"    searched as: {result.name_used}")
    for candidate in result.candidates or ((result.artist,) if result.artist else ()):
        mark = "->" if result.artist and candidate.id == result.artist.id else "  "
        link = f"https://open.spotify.com/artist/{candidate.id}"
        lines.append(f"    {mark} {candidate.name or '(override)'}  {link}")
        clues = result.clues.get(candidate.id)
        if clues:
            notes = []
            if clues.followers is not None:
                fit = {True: "fits room", False: "doesn't fit room", None: ""}[clues.fits]
                notes.append(f"{clues.followers:,} followers {fit}".strip())
            if clues.active is not None:
                notes.append("releasing lately" if clues.active else "nothing recent")
            if clues.people:
                notes.append("write-up names: " + ", ".join(clues.people))
            if clues.titles:
                notes.append("write-up mentions: " + ", ".join(clues.titles))
            if notes:
                lines.append("         " + "; ".join(notes))
    return lines + [""]


def summary(results: list[ArtistMatch]) -> str:
    how = Counter(r.how for r in results)
    status = Counter(r.status for r in results)
    out = [f"{len(results)} acts: " + ", ".join(f"{n} {s}" for s, n in status.most_common())]
    out += [f"  {n:3}  {h}" for h, n in how.most_common()]
    for label in ("unsure", "none"):
        names = [r.act for r in results if r.status == label]
        if names:
            out.append(f"{label}: " + "; ".join(names))
    return "\n".join(out)
