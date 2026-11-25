import pytest

from localshows.api import ApiError
from localshows.lastfm import LastFm


class Response:
    def __init__(self, status, data=None, headers=None):
        self.status_code, self._data, self.headers = status, data, headers or {}

    def json(self):
        if self._data is None:
            raise ValueError
        return self._data


class Session:
    def __init__(self, *responses):
        self.responses, self.headers, self.calls = list(responses), {}, 0

    def request(self, method, url, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def test_rate_limit_waits_as_asked_then_retries():
    waits = []
    tracks = {"toptracks": {"track": [{"name": "Ophelia"}]}}
    session = Session(Response(429, headers={"Retry-After": "7"}), Response(200, tracks))
    assert LastFm("k", session, sleep=waits.append).top_tracks("The Band") == ["Ophelia"]
    assert 7 in waits and session.calls == 2


def test_unknown_artist_is_empty_but_other_errors_raise():
    lastfm = LastFm("k", Session(Response(200, {"error": 6}), Response(403, {"error": 10})))
    assert lastfm.top_tracks("Nobody") == []
    with pytest.raises(ApiError):
        lastfm.top_tracks("Anybody")
