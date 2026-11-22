"""The dry-run printout."""

from localshows.config import Venue
from localshows.listings import Collected
from localshows.models import Show


def _support(show: Show) -> str:
    return ", ".join(("ft. " if a.role == "guest" else "") + a.name for a in show.support)


def render(result: Collected, venues: list[Venue]) -> str:
    names = {venue.id: venue.name for venue in venues}
    playing = [s for s in result.shows if not s.skipped and s.headliner]
    unnamed = [s for s in result.shows if not s.skipped and not s.headliner]
    skipped = [s for s in result.shows if s.skipped]

    lines = [f"{'DATE':16}{'VENUE':20}{'HEADLINER':45}OPENERS / GUESTS"]
    for show in playing:
        when, where = show.listing.day.strftime("%a %b %d %Y"), names[show.listing.venue]
        row = f"{when:16}{where:20}{show.headliner.name:45}{_support(show)}"
        lines.append(row.rstrip())

    for heading, group in (("NO ACT NAMED", unnamed), ("NOT A SHOW", skipped)):
        if group:
            lines += ["", f"{heading} (left out of playlists)"]
        for show in group:
            when, where = show.listing.day.strftime("%a %b %d %Y"), names[show.listing.venue]
            reason = f" [{show.skipped}]" if show.skipped else ""
            lines.append(f"{when:16}{where:20}{show.listing.title}{reason}")

    lines += ["", "LISTINGS READ"]
    for venue in venues:
        if venue.id in result.failures:
            lines.append(f"{venue.name:20}FAILED: {result.failures[venue.id]}")
        else:
            lines.append(f"{venue.name:20}{result.counts.get(venue.id, 0)}")
    lines.append(
        f"{len(playing)} shows with an act, {len(unnamed)} without, {len(skipped)} skipped"
    )
    return "\n".join(lines)
