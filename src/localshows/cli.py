"""Command line entry point."""

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from localshows import listings, match_report, report, secrets
from localshows.config import load_venues
from localshows.lastfm import LastFm
from localshows.spotify import Spotify
from localshows.web import Web


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="localshows")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repo directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("venues", help="list the configured venues")
    dry_run = commands.add_parser(
        "dry-run", help="print the next 12 months of shows; never touches Spotify"
    )
    dry_run.add_argument("--venue", action="append", help="only this venue id (repeatable)")
    match = commands.add_parser(
        "match", help="find each act's Spotify artist; details go to local/matches.txt"
    )
    match.add_argument("--venue", action="append", help="only this venue id (repeatable)")
    args = parser.parse_args(argv)

    venues = load_venues(args.root)
    if args.command == "venues":
        for venue in venues:
            print(f"{venue.name:20} {venue.town:12} {venue.url}")
        return 0

    if args.venue:
        if unknown := set(args.venue) - {venue.id for venue in venues}:
            parser.error(f"unknown venue: {', '.join(sorted(unknown))}")
        venues = [venue for venue in venues if venue.id in args.venue]
    today = datetime.now(ZoneInfo("America/New_York")).date()
    result = listings.collect(venues, Web(), today)
    if args.command == "dry-run":
        print(report.render(result, venues))
        return 1 if result.failures else 0

    keys = secrets.load_env(args.root)
    client_id, client_secret, lastfm_key = secrets.require(
        keys, "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "LASTFM_API_KEY"
    )
    for venue_id, error in result.failures.items():
        print(f"not read: {venue_id}: {error}")
    found, path = match_report.run(
        result.shows, Spotify(client_id, client_secret), LastFm(lastfm_key), args.root
    )
    print(match_report.summary(found))
    print(f"details: {path}")
    return 1 if result.failures else 0
