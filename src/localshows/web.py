"""Polite fetching: an honest user agent, robots.txt, and each site's crawl delay."""

import time
from urllib.parse import urlsplit

import requests
from protego import Protego

USER_AGENT = "event-listings-reader/0.1"
DEFAULT_DELAY = 1.0


class ReadError(Exception):
    """A venue couldn't be read. This never means that it has no shows."""


class Web:
    def __init__(self, session: requests.Session | None = None, sleep=time.sleep):
        self._session = session or requests.Session()
        self._session.headers["User-Agent"] = USER_AGENT
        self._sleep = sleep
        self._robots: dict[str, Protego] = {}
        self._last: dict[str, float] = {}

    def _request(self, url: str) -> requests.Response:
        try:
            return self._session.get(url, timeout=30)
        except requests.RequestException as error:
            raise ReadError(f"{url}: {type(error).__name__}") from error

    def check_allowed(self, url: str) -> float:
        """Raise if robots.txt disallows url; otherwise return the delay it asks for."""
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            response = self._request(f"{origin}/robots.txt")
            if response.status_code in (401, 403, 429) or response.status_code >= 500:
                raise ReadError(f"{origin}/robots.txt: HTTP {response.status_code}")
            rules = response.text if response.status_code == 200 else ""
            self._robots[origin] = Protego.parse(rules)
            self._last[origin] = time.monotonic()
        rules = self._robots[origin]
        if not rules.can_fetch(url, USER_AGENT):
            raise ReadError(f"{url}: disallowed by robots.txt")
        return rules.crawl_delay(USER_AGENT) or DEFAULT_DELAY

    def get(self, url: str) -> str:
        delay = self.check_allowed(url)
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        wait = self._last.get(origin, float("-inf")) + delay - time.monotonic()
        if wait > 0:
            self._sleep(wait)
        response = self._request(url)
        self._last[origin] = time.monotonic()
        # A bot challenge can answer 202 with an empty body, so only a real 200 counts.
        if response.status_code != 200 or not response.content:
            raise ReadError(f"{url}: HTTP {response.status_code}, {len(response.content)} bytes")
        # A redirect must not carry us somewhere robots.txt rules out.
        if response.url != url:
            self.check_allowed(response.url)
        response.encoding = "utf-8"
        return response.text
