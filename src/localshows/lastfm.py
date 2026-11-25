"""Last.fm, for each artist's most-played songs. Song data courtesy of Last.fm."""

from localshows.api import Api, ApiError

URL = "https://ws.audioscrobbler.com/2.0/"
NOT_FOUND = 6


class LastFm:
    def __init__(self, key: str, session=None, sleep=None):
        kwargs = {"sleep": sleep} if sleep else {}
        self._api = Api(session, spacing=0.25, **kwargs)
        self._key = key
        self._cache: dict[str, list[str]] = {}

    def top_tracks(self, artist: str, limit: int = 10) -> list[str]:
        """Song titles, most played first; empty if Last.fm doesn't know the artist."""
        if artist not in self._cache:
            params = {
                "method": "artist.gettoptracks",
                "artist": artist,
                "autocorrect": 0,
                "limit": limit,
                "api_key": self._key,
                "format": "json",
            }
            response = self._api.request("GET", URL, params=params)
            try:
                data = response.json()
            except ValueError as error:
                raise ApiError(f"Last.fm: HTTP {response.status_code}, not JSON") from error
            if data.get("error") == NOT_FOUND:
                self._cache[artist] = []
            elif "error" in data or response.status_code != 200:
                raise ApiError(f"Last.fm error {data.get('error')}: {data.get('message')}")
            else:
                tracks = data.get("toptracks", {}).get("track", [])
                if isinstance(tracks, dict):
                    tracks = [tracks]
                self._cache[artist] = [track["name"] for track in tracks if track.get("name")]
        return self._cache[artist]
