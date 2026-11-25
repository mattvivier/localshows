"""JSON over HTTP for the music services, with rate-limit backoff."""

import time

import requests

from localshows.web import USER_AGENT


class ApiError(Exception):
    pass


class Api:
    def __init__(self, session: requests.Session | None, spacing: float, sleep=time.sleep):
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._spacing = spacing
        self._sleep = sleep
        self._last = float("-inf")

    def request(self, method: str, url: str, *, tries: int = 4, **kwargs) -> requests.Response:
        for attempt in range(tries):
            wait = self._last + self._spacing - time.monotonic()
            if wait > 0:
                self._sleep(wait)
            try:
                response = self.session.request(method, url, timeout=30, **kwargs)
            except requests.RequestException as error:
                if attempt == tries - 1:
                    raise ApiError(f"{url}: {type(error).__name__}") from error
                self._sleep(2**attempt)
                continue
            finally:
                self._last = time.monotonic()
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < tries - 1:
                    retry = response.headers.get("Retry-After", "")
                    self._sleep(min(float(retry) if retry.isdigit() else 2**attempt, 120))
                    continue
            return response
        raise AssertionError("unreachable")
