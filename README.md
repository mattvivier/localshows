# LocalShows

A personal tool for knowing who's coming to town and what they sound like.

It reads upcoming shows from the websites of a few venues in Woodstock and
Saugerties, NY, and will keep a Spotify playlist for each one.

**Status:** setup. Listings, song picking, playlists and the daily run come next.

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
