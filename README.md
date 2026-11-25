# LocalShows

A personal tool for knowing who's coming to town and what they sound like.

It reads upcoming shows from the websites of a few venues in Woodstock and
Saugerties, NY, and will keep a Spotify playlist for each one.

**Status:** listings and Spotify artist matching work. Song picking, playlists and the
daily run come next.

```sh
.venv/bin/localshows dry-run                      # the next 12 months, every venue
.venv/bin/localshows dry-run --venue bearsville   # just one
.venv/bin/localshows match                        # each act's Spotify artist
```

`match` needs API keys in a `.env` file at the repo root (gitignored):

```
LASTFM_API_KEY=
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
```

It writes its findings to `local/matches.txt`. An act is matched by fuzzy name, and
when several Spotify artists share the name, by which one has the name's most-played
songs on Last.fm. Acts that can't be told apart are left out rather than guessed.
`config/overrides.json` can pin or skip an act, but is meant to stay empty.

Colony's calendar is drawn by a script, so reading it needs Google Chrome installed.
Titles are turned into headliners and openers by rules and fuzzy matching
(`billing.py`, `fuzzy.py`). There are no hand-kept lists of shows.

## Development

Requires Python 3.12 or newer.

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/localshows venues
.venv/bin/pytest
.venv/bin/ruff check .
```

## Layout

- `config/venues.json`: the venues and where each one lists its shows
- `state/`: JSON written by the pipeline and committed, so changes have a history
- `src/localshows/`: the code

Song data courtesy of [Last.fm](https://www.last.fm).
