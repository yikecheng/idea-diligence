"""Find public discussion leads through Hacker News Search by Algolia."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from http.client import HTTPException, RemoteDisconnected
from queue import Empty, Queue
from threading import Thread
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

SEARCH_URL = "https://hn.algolia.com/api/v1/search"
MAX_HITS = 5
MAX_RESPONSE_BYTES = 256 * 1024
TIMEOUT_SECONDS = 9.0
FIRST_ATTEMPT_SECONDS = 3.5
_RETRYABLE_HTTP_STATUS = {408, 500, 502, 503, 504}
_SENSITIVE_QUERY = re.compile(
    r"@|\b[a-z][a-z0-9+.-]*://|\bwww\.|"
    r"\b[a-z0-9.-]+\.(?:com|org|net|edu|gov|io|ai)\b|"
    r"\b(?:sk[-_]|tvly-|gh[pousr]_|github_pat_|xox[baprs]-|AKIA)[a-z0-9_-]{8,}",
    re.IGNORECASE,
)


class PublicSearchError(ValueError):
    """A user-facing validation or provider failure message."""


class _TransientSearchError(PublicSearchError):
    """A provider failure which may improve on the next attempt."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Keep the search query on the documented provider.
        return None


def _clean_query(query: str) -> str:
    if not isinstance(query, str) or any(ord(char) < 32 and not char.isspace() for char in query):
        raise PublicSearchError("Enter a public search topic in plain text.")
    clean = " ".join(query.split())
    if not 3 <= len(clean) <= 120:
        raise PublicSearchError("Enter a public search topic between 3 and 120 characters.")
    if _SENSITIVE_QUERY.search(clean):
        raise PublicSearchError("Search with public topic words. Remove email addresses, URLs, and keys.")
    return clean


def _request_hits(query: str) -> list:
    deadline = monotonic() + TIMEOUT_SECONDS
    request = Request(
        SEARCH_URL + "?" + urlencode({"query": query, "tags": "story", "hitsPerPage": MAX_HITS}),
        headers={"Accept": "application/json", "User-Agent": "IdeaDiligence/1.0"},
    )
    try:
        return _get_hits(request, min(FIRST_ATTEMPT_SECONDS, deadline - monotonic()))
    except _TransientSearchError as first_error:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise PublicSearchError(str(first_error)) from None
    try:
        return _get_hits(request, remaining)
    except _TransientSearchError as error:
        raise PublicSearchError(str(error)) from None


def _get_hits(request: Request, timeout: float) -> list:
    if timeout <= 0:
        raise _TransientSearchError("Hacker News search took too long. Try again when the connection is stable.")
    results: Queue[list | PublicSearchError] = Queue(maxsize=1)

    def fetch() -> None:
        try:
            with build_opener(_RejectRedirects).open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise PublicSearchError("Hacker News search returned more data than this workspace can display.")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or not isinstance(payload.get("hits"), list):
                raise PublicSearchError("Hacker News search returned an unexpected response.")
            results.put(payload["hits"])
        except PublicSearchError as error:
            results.put(error)
        except HTTPError as error:
            status = error.code
            error.close()
            if status == 429:
                failure = PublicSearchError("Hacker News search is rate limited. Wait a moment before trying again.")
            elif status in _RETRYABLE_HTTP_STATUS:
                failure = _TransientSearchError(
                    f"Hacker News search is temporarily unavailable (HTTP {status}). Try again later."
                )
            else:
                failure = PublicSearchError(f"Hacker News search returned HTTP {status}. Try again later.")
            results.put(failure)
        except (TimeoutError, ConnectionResetError, RemoteDisconnected):
            results.put(_TransientSearchError("Hacker News search took too long or was interrupted. Try again shortly."))
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, ConnectionResetError)):
                results.put(_TransientSearchError("Hacker News search took too long or was interrupted. Try again shortly."))
            else:
                results.put(PublicSearchError("Could not reach Hacker News search. Check the connection and try again."))
        except (HTTPException, OSError):
            results.put(PublicSearchError("Could not reach Hacker News search. Check the connection and try again."))
        except (ValueError, RecursionError):
            results.put(PublicSearchError("Hacker News search returned an unexpected response."))

    Thread(target=fetch, daemon=True).start()
    try:
        response = results.get(timeout=timeout)
    except Empty:
        raise _TransientSearchError("Hacker News search took too long. Try again when the connection is stable.") from None
    if isinstance(response, PublicSearchError):
        raise response
    return response


def _discussion_metadata(hit: dict) -> str:
    fields = ["Hacker News discussion"]
    posted = hit.get("created_at")
    if isinstance(posted, str):
        try:
            fields.append(f"Posted {date.fromisoformat(posted[:10]).isoformat()}")
        except ValueError:
            pass
    count = hit.get("num_comments")
    if type(count) is int and 0 <= count <= 1_000_000:
        fields.append(f"{count} comment{'' if count == 1 else 's'}")
    return " · ".join(fields)


def search_discussions(query: str) -> list[dict[str, str]]:
    """Return live HN story references as leads, with their observed metadata."""
    hits = _request_hits(_clean_query(query))
    retrieved_at = datetime.now(timezone.utc).date().isoformat()
    leads = []
    seen = set()
    for hit in hits[:MAX_HITS]:
        if not isinstance(hit, dict):
            continue
        item_id, title = hit.get("objectID"), hit.get("title")
        if not isinstance(item_id, str) or not re.fullmatch(r"[1-9][0-9]{0,15}", item_id):
            continue
        if item_id in seen or not isinstance(title, str) or not title.strip():
            continue
        title = " ".join(title.split())
        if len(title) > 180:
            title = title[:179].rstrip() + "…"
        seen.add(item_id)
        leads.append({
            "title": title,
            "url": f"https://news.ycombinator.com/item?id={item_id}",
            "passage": _discussion_metadata(hit),
            "kind": "discussion_lead",
            "retrieved_at": retrieved_at,
        })
    return leads
