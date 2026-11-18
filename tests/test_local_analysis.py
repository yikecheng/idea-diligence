import pytest

from idea_diligence.local_analysis import build_local_analysis
from idea_diligence.storage import (
    load_run,
    load_workspace,
    save_evidence_review,
    save_experiment_outcome,
    save_founder_plan,
    save_run,
)


BRIEF = {
    "title": "Shift change digest",
    "customer": "Volunteer coordinators",
    "problem": "Coordinators miss late staffing changes.",
    "solution": "A shared digest for handoffs.",
}
ASSUMPTIONS = [
    {"category": "feasibility", "statement": "The digest can be prepared in ten minutes.", "impact": 3, "uncertainty": 2},
    {"category": "desirability", "statement": "Coordinators return for a second handoff.", "impact": 5, "uncertainty": 5},
]
EXCERPT = {
    "assumption_id": "A2",
    "title": "A coordinator's source",
    "url": "https://example.com/notes",
    "passage": "A weekly schedule is available.",
    "stance": "supports",
    "reason": "A published schedule may be a useful source for the digest.",
}
EXPERIMENT = {
    "title": "Observe a second handoff",
    "procedure": "Observe a second handoff without a reminder.",
    "metric": "A second handoff requested by the same coordinator",
    "threshold": "A coordinator returns and requests the handoff unprompted",
    "time": "One week",
    "cost": "Staff time",
}
LEAD = {
    "title": "Discussion title",
    "url": "https://news.ycombinator.com/item?id=123456",
    "passage": "Hacker News discussion · 8 comments",
    "kind": "discussion_lead",
    "retrieved_at": "2026-11-18",
}


def test_custom_brief_keeps_founder_evidence_as_context_and_search_as_unlinked():
    report = build_local_analysis(
        BRIEF, ASSUMPTIONS, [EXCERPT], EXPERIMENT,
        leads=[LEAD, LEAD], discovery_queries=["volunteer handoffs"],
    )
    assert report["mode"] == "local"
    assert [(r["id"], r["risk"], r["status"]) for r in report["assumptions"]] == [
        ("A2", 25, "context"), ("A1", 6, "open"),
    ]
    assert report["experiment"]["assumption_id"] == "A2"
    assert [source["kind"] for source in report["sources"]] == ["founder_supplied", "discussion_lead"]
    assert report["links"] == [{
        "assumption_id": "A2", "source_id": "S1", "stance": "context",
        "reason": "Founder annotation: possible support. A published schedule may be a useful source for the digest.",
    }]
    assert report["usage"]["model_calls"] == 0
    assert report["usage"]["search_calls"] == 1
    assert "volunteer handoffs" not in repr(report["trace"])


def test_custom_workspace_persists_decisions_separately_from_original_snapshot(tmp_path):
    report = build_local_analysis(BRIEF, ASSUMPTIONS, [EXCERPT], {**EXPERIMENT, "assumption_id": "A1"})
    assert report["experiment"]["assumption_id"] == "A1"
    path = tmp_path / "runs.sqlite3"
    run_id = save_run(report, path)
    save_evidence_review(run_id, "A2", "S1", "accept", "Inspect again after the test.", path)
    save_experiment_outcome(run_id, "completed", 7, 3, "One-week result", "revise", path)
    workspace = load_workspace(run_id, path)
    assert workspace["reviews"][0]["verdict"] == "accept"
    assert workspace["outcome"]["decision"] == "revise"
    assert load_run(run_id, path) == report


@pytest.mark.parametrize(("assumptions", "evidence", "experiment", "leads", "message"), [
    ([], [], None, (), "assumptions"),
    ([{**ASSUMPTIONS[0], "impact": True}], [], None, (), "scores"),
    (ASSUMPTIONS, [{**EXCERPT, "assumption_id": "A4"}], None, (), "existing assumption"),
    (ASSUMPTIONS, [{**EXCERPT, "url": "http://127.0.0.1"}], None, (), "public HTTP"),
    (ASSUMPTIONS, [EXCERPT, EXCERPT], None, (), "already linked"),
    (ASSUMPTIONS, [], {**EXPERIMENT, "metric": ""}, (), "measure"),
    (ASSUMPTIONS, [], None, [{**LEAD, "url": "https://example.com/123"}], "Hacker News item link"),
])
def test_invalid_custom_inputs_have_actionable_errors(assumptions, evidence, experiment, leads, message):
    with pytest.raises(ValueError, match=message):
        build_local_analysis(BRIEF, assumptions, evidence, experiment, leads=leads)


def test_brief_can_be_created_before_selecting_experiment_or_collecting_evidence():
    report = build_local_analysis(BRIEF, [ASSUMPTIONS[0]], [], None)
    assert report["mode"] == "local"
    assert report["assumptions"][0]["status"] == "open"
    assert not report["sources"]
    assert not report["links"]
    assert report["experiment"] is None
    assert report["usage"]["search_calls"] == 0


def test_add_founder_plan_after_the_run_and_link_a_later_outcome(tmp_path):
    original = build_local_analysis(BRIEF, ASSUMPTIONS, [], None)
    path = tmp_path / "runs.sqlite3"
    run_id = save_run(original, path)
    assert load_workspace(run_id, path)["plan"] is None

    with pytest.raises(ValueError, match="existing assumption"):
        save_founder_plan(run_id, {**EXPERIMENT, "assumption_id": "A5"}, path)
    with pytest.raises(ValueError, match="decision threshold"):
        save_founder_plan(run_id, {**EXPERIMENT, "threshold": ""}, path)
    assert load_workspace(run_id, path)["plan"] is None

    plan = save_founder_plan(run_id, {**EXPERIMENT, "assumption_id": "A1"}, path)
    assert plan == {**EXPERIMENT, "assumption_id": "A1"}
    assert load_workspace(run_id, path)["plan"] == plan
    assert load_run(run_id, path) == original
    with pytest.raises(ValueError, match="already has an experiment"):
        save_founder_plan(run_id, {**plan, "threshold": "Easier criterion"}, path)

    result = save_experiment_outcome(run_id, "completed", 7, 3, "Observed handoff", "revise", path)
    workspace = load_workspace(run_id, path)
    assert workspace["outcome"] == result
    assert workspace["outcome"]["assumption_id"] == "A1"
    assert workspace["plan"] == plan
    assert load_run(run_id, path) == original


def test_plan_can_neither_replace_an_original_experiment_nor_target_an_empty_run(tmp_path):
    path = tmp_path / "runs.sqlite3"
    report = build_local_analysis(BRIEF, ASSUMPTIONS, [], EXPERIMENT)
    run_id = save_run(report, path)
    with pytest.raises(ValueError, match="already has an experiment"):
        save_founder_plan(run_id, EXPERIMENT, path)
    assert load_workspace(run_id, path)["plan"] is None

    empty = save_run({**report, "experiment": None, "assumptions": []}, path)
    with pytest.raises(ValueError, match="needs an assumption"):
        save_founder_plan(empty, EXPERIMENT, path)
