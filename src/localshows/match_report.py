"""Match every billed act, and write the details for a person to read.

Spotify's names and links go only to the gitignored report file; the console gets
counts and the venues' own act names.
"""

from collections import Counter
from pathlib import Path

from localshows import state
from localshows.fuzzy import normalize
from localshows.matching import ArtistMatch, match_act, overrides_from
from localshows.models import Act, Show


def unique_acts(shows: list[Show]) -> list[tuple[Act, Show]]:
    seen: dict[str, tuple[Act, Show]] = {}
    for show in sorted(shows, key=lambda s: (s.listing.day, s.listing.venue)):
        for act in show.acts:
            seen.setdefault(normalize(act.name), (act, show))
    return list(seen.values())


def run(shows: list[Show], spotify, lastfm, root: Path) -> tuple[list[ArtistMatch], Path]:
    overrides = overrides_from(state.load(root / "config" / "overrides.json", {}))
    acts = unique_acts(shows)
    results, lines = [], []
    for act, show in acts:
        result = match_act(act, spotify, lastfm, overrides)
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
        votes = result.votes.get(candidate.id, 0)
        songs = f"  {votes}/{result.songs_checked} top songs" if result.songs_checked else ""
        link = f"https://open.spotify.com/artist/{candidate.id}"
        lines.append(f"    {mark} {candidate.name or '(override)'}  {link}{songs}")
    return lines + [""]


def summary(results: list[ArtistMatch]) -> str:
    how = Counter(r.how.split(",")[0] for r in results)
    status = Counter(r.status for r in results)
    out = [f"{len(results)} acts: " + ", ".join(f"{n} {s}" for s, n in status.most_common())]
    out += [f"  {n:3}  {h}" for h, n in how.most_common()]
    for label in ("unsure", "none"):
        names = [r.act for r in results if r.status == label]
        if names:
            out.append(f"{label}: " + "; ".join(names))
    return "\n".join(out)
