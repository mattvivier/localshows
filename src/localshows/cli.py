"""Command line entry point."""

import argparse
from pathlib import Path

from localshows.config import load_venues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="localshows")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repo directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("venues", help="list the configured venues")
    args = parser.parse_args(argv)

    for venue in load_venues(args.root):
        print(f"{venue.name:20} {venue.town:12} {venue.url}")
    return 0
