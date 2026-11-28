"""Spotify Web API. Search needs only the app's own credentials, not a user login."""

import time
from dataclasses import dataclass, field
from datetime import date

from localshows.api import Api, ApiError
from localshows.fuzzy import Candidate

ACCOUNTS = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
MARKET = "US"
PAGE = 10  # the most Search and artist albums return per request
RELEASE_PAGES = 2
RELEASES_WITH_TRACKS = 8


@dataclass
class Catalog:
    """What an artist has put out: titles, the other artists credited, the latest date."""

    titles: set[str] = field(default_factory=set)
    people: set[str] = field(default_factory=set)
    latest: date | None = None


def release_day(text: str) -> date | None:
    """Spotify gives "2019", "2019-05" or "2019-05-03"."""
    parts = (text or "").split("-")
    try:
        return date(int(parts[0]), int(parts[1]) if len(parts) > 1 else 1, 1)
    except (ValueError, IndexError):
        return None


class Spotify:
    def __init__(self, client_id: str, client_secret: str, session=None, sleep=None):
        kwargs = {"sleep": sleep} if sleep else {}
        self._api = Api(session, spacing=0.1, **kwargs)
        self._auth = (client_id, client_secret)
        self._token = ""
        self._expires = 0.0
        # Follower counts from search results; Spotify marks the field deprecated.
        self.followers: dict[str, int | None] = {}
        self._catalogs: dict[str, Catalog] = {}

    def _authorize(self) -> None:
        response = self._api.request(
            "POST", ACCOUNTS, data={"grant_type": "client_credentials"}, auth=self._auth
        )
        if response.status_code != 200:
            raise ApiError(f"Spotify login failed: HTTP {response.status_code}")
        data = response.json()
        self._token = data["access_token"]
        self._expires = time.monotonic() + data.get("expires_in", 3600) - 60

    def get(self, path: str, **params) -> dict:
        for _ in range(2):
            if time.monotonic() >= self._expires:
                self._authorize()
            response = self._api.request(
                "GET",
                f"{API}{path}",
                params=params,
                headers={"Authorization": f"Bearer {self._token}"},
            )
            if response.status_code == 401:
                self._expires = 0.0
                continue
            if response.status_code != 200:
                raise ApiError(f"Spotify {path}: HTTP {response.status_code}")
            return response.json()
        raise ApiError(f"Spotify {path}: not authorized")

    def search_artists(self, name: str, page: int = 0) -> list[Candidate]:
        data = self.get(
            "/search", q=name, type="artist", limit=PAGE, offset=page * PAGE, market=MARKET
        )
        items = [item for item in data.get("artists", {}).get("items", []) if item]
        for item in items:
            self.followers[item["id"]] = (item.get("followers") or {}).get("total")
        return [Candidate(item["id"], item["name"]) for item in items]

    def catalog(self, artist_id: str) -> Catalog:
        if artist_id in self._catalogs:
            return self._catalogs[artist_id]
        found = Catalog()

        def credit(artists: list[dict]) -> None:
            found.people |= {
                a["name"] for a in artists if a.get("id") != artist_id and a.get("name")
            }

        releases = []
        for page in range(RELEASE_PAGES):
            data = self.get(
                f"/artists/{artist_id}/albums",
                include_groups="album,single",
                limit=PAGE,
                offset=page * PAGE,
                market=MARKET,
            )
            items = [item for item in data.get("items", []) if item]
            releases += items
            if len(items) < PAGE:
                break
        for release in releases:
            found.titles.add(release.get("name", ""))
            credit(release.get("artists", []))
            day = release_day(release.get("release_date", ""))
            if day and (found.latest is None or day > found.latest):
                found.latest = day
        # Whose records this artist plays on.
        data = self.get(
            f"/artists/{artist_id}/albums", include_groups="appears_on", limit=PAGE, market=MARKET
        )
        for release in data.get("items", []):
            if release:
                credit(release.get("artists", []))
        for release in releases[:RELEASES_WITH_TRACKS]:
            data = self.get(f"/albums/{release['id']}/tracks", limit=50, market=MARKET)
            for track in data.get("items", []):
                if track:
                    found.titles.add(track.get("name", ""))
                    credit(track.get("artists", []))
        found.titles.discard("")
        self._catalogs[artist_id] = found
        return found

    def search_tracks(self, title: str, artist: str) -> list[dict]:
        query = f'track:"{title}" artist:"{artist}"'
        data = self.get("/search", q=query, type="track", limit=PAGE, market=MARKET)
        return [item for item in data.get("tracks", {}).get("items", []) if item]
