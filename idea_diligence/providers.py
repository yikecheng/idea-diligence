"""Small HTTP adapters with bounded, inspectable provider calls."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from http.client import HTTPException
from queue import Empty, Queue
from threading import Thread
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

OPENAI_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.4-mini"
MODEL_REQUEST_BYTES = 32 * 1024
MAX_COMPLETION_TOKENS = 2_500
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
SEARCH_RESULTS = 3
MODEL_TIMEOUT = 32.0
SEARCH_TIMEOUT = 10.0


class ProviderError(RuntimeError):
    """A sanitized message suitable for the user interface."""


@dataclass(frozen=True, repr=False)
class ProviderConfig:
    model_key: str
    search_key: str
    model: str
    base_url: str

    @classmethod
    def from_env(cls) -> ProviderConfig:
        return cls(
            model_key=os.environ.get("OPENAI_API_KEY", "").strip(),
            search_key=os.environ.get("TAVILY_API_KEY", "").strip(),
            model=os.environ.get("OPENAI_MODEL", "").strip() or DEFAULT_MODEL,
            base_url=os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/") or OPENAI_BASE,
        )

    @property
    def ready(self) -> bool:
        return bool(self.model_key and self.search_key)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer token to a redirect destination.
        return None


def _post(
    provider: str, url: str, key: str, data: bytes, timeout: float
) -> dict[str, Any]:
    if timeout <= 0:
        raise ProviderError(f"{provider} was skipped because the run reached its time limit.")

    mailbox: Queue[dict[str, Any] | ProviderError] = Queue(maxsize=1)

    def request_json() -> None:
        try:
            endpoint = urlsplit(url)
            if (
                endpoint.scheme != "https"
                or not endpoint.hostname
                or endpoint.username is not None
                or endpoint.password is not None
                or endpoint.query
                or endpoint.fragment
            ):
                raise ProviderError(f"{provider} needs an HTTPS API endpoint without embedded credentials.")
            request = Request(
                url, data=data, method="POST",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            )
            with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ProviderError(f"{provider} returned more than the response size limit.")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise ProviderError(f"{provider} returned an unexpected response format.")
            mailbox.put(parsed)
        except ProviderError as error:
            mailbox.put(error)
        except HTTPError as error:
            code = error.code
            error.close()
            mailbox.put(ProviderError(f"{provider} returned HTTP {code}."))
        except (HTTPException, TimeoutError, URLError, OSError):
            mailbox.put(ProviderError(f"{provider} could not be reached within this run."))
        except (TypeError, ValueError, RecursionError):
            mailbox.put(ProviderError(f"{provider} returned an unexpected response format."))

    # Socket timeouts alone do not cap the total elapsed time if bytes keep arriving.
    Thread(target=request_json, daemon=True).start()
    try:
        result = mailbox.get(timeout=timeout)
    except Empty:
        raise ProviderError(f"{provider} reached its request time limit.") from None
    if isinstance(result, ProviderError):
        raise result
    return result


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def model_json(
    config: ProviderConfig,
    *,
    name: str,
    instructions: str,
    inputs: dict[str, Any],
    schema: dict[str, Any],
    timeout: float,
    usage: dict[str, Any],
) -> dict[str, Any]:
    request = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": _json_bytes(inputs).decode("utf-8")},
        ],
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": name, "strict": True, "schema": schema},
        },
    }
    if config.model.startswith(("gpt-5-mini", "gpt-5.4-mini")):
        request["reasoning_effort"] = "low"
    data = _json_bytes(request)
    if len(data) > MODEL_REQUEST_BYTES:
        raise ProviderError("The model request exceeded the 32 KiB payload limit.")
    if timeout <= 0:
        raise ProviderError("The language model was skipped because the run reached its time limit.")
    usage["model_calls"] += 1
    result = _post("Language model", f"{config.base_url}/chat/completions", config.model_key,
                   data, min(timeout, MODEL_TIMEOUT))
    reported = result.get("usage")
    if isinstance(reported, dict):
        for field, key in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
            value = reported.get(field)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                usage[key] += value
    try:
        choice = result["choices"][0]
        message = choice["message"]
        if choice.get("finish_reason") != "stop" or message.get("refusal"):
            raise ProviderError("The model did not finish a structured response within its limits.")
        parsed = json.loads(message["content"])
        if not isinstance(parsed, dict):
            raise ValueError
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        raise ProviderError("The model returned an invalid structured response.") from None
    return parsed


def search_web(config: ProviderConfig, query: str, timeout: float) -> list[dict[str, Any]]:
    data = _json_bytes({
        "query": query,
        "search_depth": "basic",
        "auto_parameters": False,
        "chunks_per_source": 1,
        "max_results": SEARCH_RESULTS,
        "include_raw_content": "markdown",
        "include_answer": False,
        "include_images": False,
        "safe_search": True,
    })
    result = _post("Tavily search", "https://api.tavily.com/search", config.search_key,
                   data, min(timeout, SEARCH_TIMEOUT))
    matches = result.get("results")
    if not isinstance(matches, list):
        raise ProviderError("Tavily returned an invalid result list.")
    return [match for match in matches[:SEARCH_RESULTS] if isinstance(match, dict)]
