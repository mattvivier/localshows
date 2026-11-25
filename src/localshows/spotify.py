"""Spotify Web API. Search needs only the app's own credentials, not a user login."""

import time

from localshows.api import Api, ApiError
from localshows.fuzzy import Candidate

ACCOUNTS = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"
MARKET = "US"
PAGE = 10  # the most Search returns per request


class Spotify:
    def __init__(self, client_id: str, client_secret: str, session=None, sleep=None):
        kwargs = {"sleep": sleep} if sleep else {}
        self._api = Api(session, spacing=0.1, **kwargs)
        self._auth = (client_id, client_secret)
        self._token = ""
        self._expires = 0.0

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
        items = data.get("artists", {}).get("items", [])
        return [Candidate(item["id"], item["name"]) for item in items if item]

    def search_tracks(self, title: str, artist: str) -> list[dict]:
        query = f'track:"{title}" artist:"{artist}"'
        data = self.get("/search", q=query, type="track", limit=PAGE, market=MARKET)
        return [item for item in data.get("tracks", {}).get("items", []) if item]
