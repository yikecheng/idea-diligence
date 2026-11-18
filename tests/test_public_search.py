"""Exercise public discussion discovery without relying on network availability."""

import json
from contextlib import contextmanager
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest

from idea_diligence import public_search


@pytest.mark.parametrize(
    "query",
    ["  x ", "a" * 121, "hello\x00 world", "founder@example.com", "https://example.com/sale",
     "example.org", "sk-proj-abcdefghijklmnop", "tvly-augmentedsearchkey"],
)
def test_invalid_query_never_reaches_provider(monkeypatch, query):
    monkeypatch.setattr(public_search, "_request_hits", lambda _query: pytest.fail("Unexpected request"))
    with pytest.raises(public_search.PublicSearchError):
        public_search.search_discussions(query)


def test_provider_hits_become_only_discussion_leads(monkeypatch):
    def fake_hits(query):
        assert query == "AI podcast"
        return [
            {"objectID": "41221242", "title": "  Show HN:  Anycast+  ", "created_at": "2024-08-12T04:49:02Z",
             "num_comments": 1, "url": "https://untrusted.example/landing"},
            {"objectID": "41221242", "title": "Duplicate"},
            {"objectID": "1&tracking=unexpected", "title": "Invalid identifier"},
            {"objectID": "32908472", "title": "Another discussion", "created_at": "unknown", "num_comments": True},
            {"objectID": "12345", "title": None},
            {"objectID": "12346", "title": "Beyond bounded result count"},
        ]

    monkeypatch.setattr(public_search, "_request_hits", fake_hits)
    leads = public_search.search_discussions(" AI   podcast ")
    assert [lead["url"] for lead in leads] == [
        "https://news.ycombinator.com/item?id=41221242",
        "https://news.ycombinator.com/item?id=32908472",
    ]
    assert leads[0]["title"] == "Show HN: Anycast+"
    assert leads[0]["passage"] == "Hacker News discussion · Posted 2024-08-12 · 1 comment"
    assert leads[1]["passage"] == "Hacker News discussion"
    assert all(lead["kind"] == "discussion_lead" for lead in leads)
    assert all(lead["retrieved_at"] for lead in leads)


def _fake_opener(monkeypatch, body):
    class Response:
        def read(self, limit):
            assert limit == public_search.MAX_RESPONSE_BYTES + 1
            return body[:limit]

    class Opener:
        @contextmanager
        def open(self, request, timeout):
            url = urlsplit(request.full_url)
            assert (url.scheme, url.netloc, url.path) == ("https", "hn.algolia.com", "/api/v1/search")
            assert parse_qs(url.query) == {
                "query": ["AI podcast"], "tags": ["story"], "hitsPerPage": ["5"],
            }
            assert request.get_method() == "GET"
            assert timeout == public_search.FIRST_ATTEMPT_SECONDS
            yield Response()

    monkeypatch.setattr(public_search, "build_opener", lambda _handler: Opener())


def test_bounded_transport_accepts_a_valid_empty_response(monkeypatch):
    _fake_opener(monkeypatch, json.dumps({"hits": []}).encode())
    assert public_search.search_discussions("AI podcast") == []


@pytest.mark.parametrize("body", [b"<html>Not JSON</html>", b'{"hits":null}', b"x" * (256 * 1024 + 1)])
def test_malformed_or_large_provider_response_has_clean_error(monkeypatch, body):
    _fake_opener(monkeypatch, body)
    with pytest.raises(public_search.PublicSearchError, match="Hacker News search returned"):
        public_search.search_discussions("AI podcast")


def test_network_error_excludes_private_exception_text(monkeypatch):
    class Offline:
        def open(self, request, timeout):
            raise URLError("internal network diagnostic")

    monkeypatch.setattr(public_search, "build_opener", lambda _handler: Offline())
    with pytest.raises(public_search.PublicSearchError, match="Could not reach Hacker News search") as error:
        public_search.search_discussions("AI podcast")
    assert "internal network diagnostic" not in str(error.value)


@pytest.mark.parametrize("first_error", [TimeoutError(), HTTPError("", 503, "opaque", {}, None)])
def test_transient_error_retries_once_with_remaining_deadline(monkeypatch, first_error):
    attempts = []

    class Success:
        def read(self, _limit):
            return b'{"hits":[]}'

    class Transient:
        @contextmanager
        def open(self, request, timeout):
            attempts.append(timeout)
            if len(attempts) == 1:
                raise first_error
            yield Success()

    clock = iter([100.0, 100.1, 103.6])
    monkeypatch.setattr(public_search, "monotonic", lambda: next(clock))
    monkeypatch.setattr(public_search, "build_opener", lambda _handler: Transient())
    assert public_search.search_discussions("room booking") == []
    assert attempts == pytest.approx([3.5, 5.4])


def test_expired_deadline_and_rate_limit_do_not_retry(monkeypatch):
    attempts = []

    def timeout(_request, budget):
        attempts.append(budget)
        raise public_search._TransientSearchError("Search expired")

    clock = iter([100.0, 100.1, 109.1])
    with monkeypatch.context() as controlled:
        controlled.setattr(public_search, "monotonic", lambda: next(clock))
        controlled.setattr(public_search, "_get_hits", timeout)
        with pytest.raises(public_search.PublicSearchError, match="Search expired"):
            public_search.search_discussions("room booking")
    assert attempts == pytest.approx([3.5])

    class RateLimited:
        def open(self, request, timeout):
            attempts.append(timeout)
            raise HTTPError("", 429, "opaque", {}, None)

    monkeypatch.setattr(public_search, "build_opener", lambda _handler: RateLimited())
    with pytest.raises(public_search.PublicSearchError, match="rate limited"):
        public_search.search_discussions("room booking")
    assert attempts == pytest.approx([3.5, 3.5])


def test_persistent_gateway_error_stops_after_two_attempts(monkeypatch):
    attempts = []

    class Offline:
        def open(self, request, timeout):
            attempts.append(timeout)
            raise HTTPError("", 502, "opaque", {}, None)

    monkeypatch.setattr(public_search, "build_opener", lambda _handler: Offline())
    with pytest.raises(public_search.PublicSearchError, match="temporarily unavailable"):
        public_search.search_discussions("room booking")
    assert len(attempts) == 2
