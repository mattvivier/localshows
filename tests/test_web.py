from types import SimpleNamespace

import pytest

from localshows.web import ReadError, Web


class FakeSession:
    def __init__(self, pages):
        self.pages, self.headers, self.asked = pages, {}, []

    def get(self, url, timeout):
        self.asked.append(url)
        status, text = self.pages.get(url, (404, "missing"))
        return SimpleNamespace(status_code=status, text=text, content=text.encode(), url=url)


def web(pages, slept=None):
    session = FakeSession(pages)
    return Web(session, (slept if slept is not None else []).append), session


def test_disallowed_url_is_never_fetched():
    rules = "User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /*?format=ical"
    client, session = web({"https://x.test/robots.txt": (200, rules)})
    for url in ("https://x.test/api/events", "https://x.test/shows?format=ical"):
        with pytest.raises(ReadError, match="robots"):
            client.get(url)
        assert url not in session.asked


def test_unreadable_robots_blocks():
    client, session = web({"https://x.test/robots.txt": (403, "no")})
    with pytest.raises(ReadError):
        client.get("https://x.test/shows")
    assert session.asked == ["https://x.test/robots.txt"]


def test_crawl_delay_is_honored():
    slept = []
    pages = {
        "https://x.test/robots.txt": (200, "User-agent: *\nCrawl-delay: 10"),
        "https://x.test/shows": (200, "ok"),
    }
    client, _ = web(pages, slept)
    assert client.get("https://x.test/shows") == "ok"
    assert 9 < slept[0] <= 10


@pytest.mark.parametrize("answer", [(202, ""), (200, ""), (403, "no")])
def test_challenge_or_empty_page_is_an_error(answer):
    client, _ = web({"https://x.test/shows": answer})
    with pytest.raises(ReadError):
        client.get("https://x.test/shows")
