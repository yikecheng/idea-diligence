"""Exercise the live engine against scripted HTTP responses at the urllib boundary."""

import io
import json
from threading import Event, Lock
from urllib.error import HTTPError

import pytest

from idea_diligence import providers
from idea_diligence.engine import run_analysis


BRIEF = {
    "title": "Workshop Queue",
    "customer": "Managers and members of a shared woodworking shop",
    "problem": "Members cannot tell when a machine station will be free.",
    "solution": "Show current queues and alert the next member.",
    "known": "The founder has observed a queue. Repeat usage is unknown.",
}
PLAN = {"assumptions": [
    {"category": "defensibility", "statement": "Existing shop tools lack member queue notifications.",
     "impact": 5, "uncertainty": 5, "reason": "The alerts are the proposed differentiator.",
     "query": "makerspace shop management waiting list alerts"},
    {"category": "desirability", "statement": "Members return to check a second queue without reminders.",
     "impact": 5, "uncertainty": 4, "reason": "Repeat usage is needed for a useful queue status.",
     "query": "makerspace shop member queue notification workflows"},
    {"category": "feasibility", "statement": "Stations have an available status feed.",
     "impact": 4, "uncertainty": 3, "reason": "A status feed would avoid manual updates.",
     "query": "makerspace workshop station status API"},
    {"category": "viability", "statement": "Shop managers would fund another tool.",
     "impact": 3, "uncertainty": 3, "reason": "Each shop must cover the subscription.",
     "query": "makerspace management tool pricing"},
    {"category": "desirability", "statement": "Member alerts would not disrupt shop work.",
     "impact": 2, "uncertainty": 3, "reason": "The warning must be usable while wearing protection.",
     "query": "shared workshop notifications and protective equipment"},
]}
EXPERIMENT = {
    "assumption_id": "A2",
    "title": "Test voluntary queue rechecking",
    "procedure": "Invite eight members to check a staffed queue page for one week. Send no reminders.",
    "metric": "Members who independently check a second queue.",
    "threshold": "Continue if at least 4 of 8 return; otherwise interview non-returners.",
    "time": "Seven days",
    "cost": "Staff time",
}
ASSESSMENT = {"links": [
    {"assumption_id": "A1", "source_id": "S1", "stance": "challenges",
     "reason": "The product page advertises member alerts for workshop stations."},
    {"assumption_id": "A2", "source_id": "S2", "stance": "supports",
     "reason": "A search lead suggests some members check queue status."},
], "experiment": EXPERIMENT}
MATCHED_PASSAGE = "Our shop dashboard alerts members when a workshop station becomes available."


def completion(result, *, finish_reason="stop", refusal=None):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": providers.DEFAULT_MODEL,
        "choices": [{
            "index": 0,
            "finish_reason": finish_reason,
            "message": {
                "role": "assistant",
                "content": json.dumps(result),
                "refusal": refusal,
            },
        }],
        "usage": {"prompt_tokens": 270, "completion_tokens": 41, "total_tokens": 311},
    }


def search_response():
    return {
        "query": "makerspace shop management waiting list alerts",
        "response_time": 0.07,
        "request_id": "search-test",
        "results": [
            {
                "title": "Station availability alerts",
                "url": "https://example.org/shop-alerts",
                "content": MATCHED_PASSAGE,
                "raw_content": "# Membership features\n\n" + MATCHED_PASSAGE,
                "score": 0.98,
            },
            {
                "title": "Member queue use",
                "url": "https://example.net/queue",
                "content": "Some members say they check the queue when planning to use the workshop.",
                "raw_content": None,
                "score": 0.71,
            },
            {
                "title": "Malformed provider URL",
                "url": "not a public URL",
                "content": "This candidate should be ignored.",
            },
        ],
    }


class ScriptedOpener:
    """Substitute only transport I/O; retain adapter validation and orchestration."""

    def __init__(self, *, fail_query=None, refusal=None):
        self.fail_query = fail_query
        self.refusal = refusal
        self.requests = []
        self.lock = Lock()

    def open(self, request, *, timeout):
        data = json.loads(request.data)
        with self.lock:
            self.requests.append((request, data, timeout))
        if request.full_url == "https://api.openai.com/v1/chat/completions":
            name = data["response_format"]["json_schema"]["name"]
            if name == "assumption_plan":
                response = completion(PLAN)
            else:
                assert name == "evidence_assessment"
                response = completion(ASSESSMENT, refusal=self.refusal)
        else:
            assert request.full_url == "https://api.tavily.com/search"
            if data["query"] == self.fail_query:
                raise HTTPError(request.full_url, 429, "Rate limited", {}, io.BytesIO(b"secret debug details"))
            response = search_response()
        return io.BytesIO(json.dumps(response).encode("utf-8"))


def enable_live(monkeypatch, opener):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai")
    monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily")
    monkeypatch.setenv("OPENAI_BASE_URL", providers.OPENAI_BASE)
    monkeypatch.setenv("OPENAI_MODEL", providers.DEFAULT_MODEL)
    monkeypatch.setattr(providers, "build_opener", lambda *_: opener)


def test_live_pipeline_uses_expected_provider_payload_and_scopes_evidence(monkeypatch):
    opener = ScriptedOpener()
    enable_live(monkeypatch, opener)
    report = run_analysis(BRIEF, mode="live", allow_external=True)

    assert report["status"] == "complete"
    assert report["usage"]["model_calls"] == 2
    assert report["usage"]["search_calls"] == 5
    assert report["usage"]["input_tokens"] == 540
    assert report["usage"]["output_tokens"] == 82
    assert report["usage"]["estimated_model_cost_usd"] == pytest.approx(0.000774)

    model = [row for row in opener.requests if row[0].full_url.startswith(providers.OPENAI_BASE)]
    search = [row for row in opener.requests if row[0].full_url == "https://api.tavily.com/search"]
    assert len(model) == 2
    assert len(search) == 5
    for request, body, timeout in model:
        assert request.get_method() == "POST"
        assert request.get_header("Authorization") == "Bearer fake-openai"
        assert request.get_header("Content-type") == "application/json"
        assert 0 < timeout <= providers.MODEL_TIMEOUT
        assert body["model"] == providers.DEFAULT_MODEL
        assert body["reasoning_effort"] == "low"
        assert body["max_completion_tokens"] == providers.MAX_COMPLETION_TOKENS
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["messages"][0]["role"] == "system"
        assert body["messages"][1]["role"] == "user"
    assert json.loads(model[0][1]["messages"][1]["content"]) == {"brief": BRIEF}
    supplied_sources = json.loads(model[1][1]["messages"][1]["content"])["sources"]
    assert [(source["id"], source["kind"]) for source in supplied_sources] == [
        ("S1", "page_excerpt"), ("S2", "search_snippet"),
    ]
    assert supplied_sources[0]["passage"] == MATCHED_PASSAGE
    assert set(supplied_sources[0]) == {"id", "kind", "title", "passage"}

    assert {body["query"] for _, body, _ in search} == {
        row["query"] for row in PLAN["assumptions"]
    }
    for request, body, timeout in search:
        assert request.get_method() == "POST"
        assert request.get_header("Authorization") == "Bearer fake-tavily"
        assert 0 < timeout <= providers.SEARCH_TIMEOUT
        assert body == {
            "query": body["query"],
            "search_depth": "basic",
            "auto_parameters": False,
            "chunks_per_source": 1,
            "max_results": 3,
            "include_raw_content": "markdown",
            "include_answer": False,
            "include_images": False,
            "safe_search": True,
        }

    assert [row["status"] for row in report["assumptions"][:2]] == ["challenged", "context"]
    assert report["links"][1]["stance"] == "context"
    assert report["experiment"] == EXPERIMENT


def test_partial_search_preserves_other_results_and_sanitizes_provider_error(monkeypatch):
    opener = ScriptedOpener(fail_query=PLAN["assumptions"][2]["query"])
    enable_live(monkeypatch, opener)
    report = run_analysis(BRIEF, mode="live", allow_external=True)

    assert report["status"] == "partial"
    assert len(report["sources"]) == 2
    assert report["experiment"] == EXPERIMENT
    assert any("Search for A3 did not complete. Tavily search returned HTTP 429." == warning
               for warning in report["warnings"])
    assert "secret debug details" not in json.dumps(report)
    assert "fake-tavily" not in json.dumps(report)


def test_refused_assessment_preserves_research_leads_without_claims(monkeypatch):
    opener = ScriptedOpener(refusal="Private provider diagnostic")
    enable_live(monkeypatch, opener)
    report = run_analysis(BRIEF, mode="live", allow_external=True)

    assert report["status"] == "partial"
    assert len(report["sources"]) == 2
    assert report["links"] == []
    assert report["experiment"] is None
    assert {assumption["status"] for assumption in report["assumptions"]} == {"open"}
    assert any("evidence assessment stopped early" in warning for warning in report["warnings"])
    assert "Private provider diagnostic" not in json.dumps(report)


def test_request_deadline_returns_while_transport_is_still_pending(monkeypatch):
    release = Event()

    class StalledOpener:
        def open(self, request, *, timeout):
            release.wait(2)
            return io.BytesIO(b"{}")

    monkeypatch.setattr(providers, "build_opener", lambda *_: StalledOpener())
    try:
        with pytest.raises(providers.ProviderError, match="reached its request time limit"):
            providers._post("Tavily search", "https://api.tavily.com/search", "fake", b"{}", 0.03)
    finally:
        release.set()


def test_insecure_override_never_calls_transport(monkeypatch):
    def unexpected_call(*_):
        pytest.fail("Insecure endpoint attempted a network request")

    monkeypatch.setattr(providers, "build_opener", unexpected_call)
    with pytest.raises(providers.ProviderError, match="needs an HTTPS API endpoint"):
        providers._post("Language model", "http://example.org/chat/completions", "fake", b"{}", 1)
