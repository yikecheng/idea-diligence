"""A workspace can keep learning after the original analysis has been saved."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from idea_diligence import storage
from idea_diligence.engine import load_demo_brief, run_analysis


def _lead(item_id: int, comments: int = 2) -> dict:
    return {
        "title": f"Discussion {item_id}",
        "url": f"https://news.ycombinator.com/item?id={item_id}",
        "passage": f"Hacker News discussion · {comments} comments",
        "retrieved_at": "2026-11-18",
    }


@pytest.fixture
def record(tmp_path):
    path = tmp_path / "runs.sqlite3"
    report = run_analysis(load_demo_brief(), "demo")
    run_id = storage.save_run(report, path)
    return run_id, report, path


def test_public_rounds_keep_individual_results_and_deduplicate_canonical_urls(record):
    run_id, report, path = record
    old = _lead(100)
    other_run = storage.save_run({**report, "sources": [*report["sources"], {**old, "id": "S90"}]}, path)
    new = _lead(200)
    mirrored_host = {**new, "url": new["url"].replace("news", "NEWS")}
    first = storage.append_research_round(other_run, "  pitch   feedback  ", [old, new, mirrored_host], path)
    second = storage.append_research_round(other_run, "founder interview", [_lead(200, 5)], path)
    empty = storage.append_research_round(other_run, "no matches", [], path)

    assert (first["query"], first["result_count"], first["added_count"]) == ("pitch feedback", 2, 1)
    assert first["source_ids"] == ["S90", "R1"]
    assert second["source_ids"] == ["R1"] and second["added_count"] == 0
    assert second["results"][0]["passage"].endswith("5 comments")
    assert (empty["result_count"], empty["added_count"], empty["source_ids"]) == (0, 0, [])
    research = storage.load_research(other_run, path)
    assert research["rounds"] == [empty, second, first]
    assert research["sources"] == [{**new, "id": "R1", "kind": "discussion_lead"}]
    assert research["links"] == []
    assert storage.load_research(run_id, path) == {"sources": [], "links": [], "rounds": [], "activity": []}


def test_overlapping_concurrent_searches_share_one_stored_lead(record):
    run_id, _, path = record
    queries = ["pitch feedback", "startup interviews"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda query: storage.append_research_round(run_id, query, [_lead(1234567890123456)], path), queries,
        ))
    assert {result["query"] for result in results} == set(queries)
    assert [result["source_ids"] for result in results] == [["R1"], ["R1"]]
    assert sorted(result["added_count"] for result in results) == [0, 1]


def test_founder_evidence_attaches_per_assumption_and_preserves_its_provenance(record):
    run_id, report, path = record
    first, second = [row["id"] for row in report["assumptions"][:2]]
    args = ("Field notes", "https://www.example.com/field#notes", "We used it only once.")
    created = storage.add_founder_evidence(run_id, first, *args, "challenges", "One person answered.", path)
    duplicate = storage.add_founder_evidence(run_id, first, *args, "challenges", "One person answered.", path)
    reused = storage.add_founder_evidence(
        run_id, second, "Another title", "https://example.com/field/", "We  used it only once.", "context", path=path,
    )
    separate = storage.add_founder_evidence(
        run_id, first, "Field notes", "https://example.com/field/", "One team said yes.", "supports", path=path,
    )

    assert created["added"] is True and duplicate == {**created, "added": False}
    assert created["source"]["kind"] == "founder_supplied" and created["source"]["id"] == "FS1"
    assert created["link"]["stance"] == "context" and created["link"]["proposed_stance"] == "challenges"
    assert reused["source"] == created["source"] and reused["link"]["assumption_id"] == second
    assert separate["source"]["id"] == "FS2"
    additions = storage.load_research(run_id, path)
    assert additions["links"] == [created["link"], reused["link"], separate["link"]]
    assert len(additions["activity"]) == 3
    assert storage.load_run(run_id, path) == report


def test_review_and_outcome_history_keeps_prior_actions(record):
    run_id, report, path = record
    assumption = report["assumptions"][0]["id"]
    new = storage.add_founder_evidence(
        run_id, assumption, "Interview note", "https://example.org/interview", "We already do this.",
        "challenges", path=path,
    )
    source = new["source"]["id"]
    storage.save_evidence_review(run_id, assumption, source, "question", path=path)
    accepted = storage.save_evidence_review(run_id, assumption, source, "accept", "Rechecked scope", path)
    assert storage.save_evidence_review(run_id, assumption, source, "accept", "Rechecked scope", path) == accepted
    storage.save_experiment_outcome(run_id, "running", None, None, "Recruiting", path=path)
    completed = storage.save_experiment_outcome(run_id, "completed", 8, 3, "Interviews", "revise", path)

    assert storage.load_workspace(run_id, path) == {"reviews": [accepted], "outcome": completed, "plan": None}
    timeline = storage.load_research(run_id, path)["activity"]
    assert [event["kind"] for event in timeline] == [
        "experiment_outcome", "experiment_outcome", "evidence_review", "evidence_review", "founder_evidence",
    ]
    assert timeline[0]["detail"]["previous_status"] == "running"
    assert timeline[0]["detail"]["qualifying"] == 3
    assert timeline[2]["detail"]["previous_verdict"] == "question"
    assert storage.load_run(run_id, path) == report


def test_invalid_or_capped_additions_leave_no_partial_state(record, monkeypatch):
    run_id, report, path = record
    assumption = report["assumptions"][0]["id"]
    with pytest.raises(ValueError, match="public topic"):
        storage.append_research_round(run_id, "person@example.com", [_lead(100)], path)
    with pytest.raises(ValueError, match="Hacker News"):
        storage.append_research_round(run_id, "startup pitch", [{**_lead(100), "url": "https://example.com"}], path)
    monkeypatch.setattr(storage, "MAX_FOUNDER_LINKS", 0)
    with pytest.raises(ValueError, match="evidence links"):
        storage.add_founder_evidence(
            run_id, assumption, "Field notes", "https://example.com/notes", "One comment.", "context", path=path,
        )
    assert storage.load_research(run_id, path) == {"sources": [], "links": [], "rounds": [], "activity": []}

    monkeypatch.setattr(storage, "MAX_RESEARCH_ROUNDS", 1)
    first = storage.append_research_round(run_id, "first round", [_lead(100)], path)
    with pytest.raises(ValueError, match="public search rounds"):
        storage.append_research_round(run_id, "second round", [_lead(200)], path)
    research = storage.load_research(run_id, path)
    assert research["rounds"] == [first]
    assert [source["id"] for source in research["sources"]] == ["R1"]


def test_followup_trials_on_one_assumption_have_independent_outcomes(record):
    run_id, report, path = record
    other_run = storage.save_run(report, path)
    selected = report["assumptions"][-1]["id"]
    plan = {**report["experiment"], "assumption_id": selected, "threshold": "Four of six users return"}
    first = storage.save_followup_experiment(run_id, plan, path)
    second = storage.save_followup_experiment(run_id, {**plan, "title": "Repeat on cohort B"}, path)
    with pytest.raises(ValueError, match="identical follow-up"):
        storage.save_followup_experiment(run_id, plan, path)
    with pytest.raises(ValueError, match="does not belong"):
        storage.save_followup_outcome(other_run, first["id"], "planned", None, None, path=path)
    with pytest.raises(ValueError, match="cannot exceed"):
        storage.save_followup_outcome(run_id, first["id"], "completed", 3, 4, path=path)

    previous = storage.save_followup_outcome(run_id, first["id"], "running", None, None, path=path)
    result = storage.save_followup_outcome(run_id, first["id"], "completed", 6, 4, "Usability sessions", "continue", path)
    assert len(storage.load_research(run_id, path)["activity"]) == 4
    assert storage.list_followup_experiments(run_id, path) == [second, {**first, "outcome": result}]
    assert result["assumption_id"] == selected and result["decision"] == "continue"
    assert first["plan"]["threshold"] == "Four of six users return"
    assert storage.load_workspace(run_id, path)["outcome"] is None
    assert storage.load_run(run_id, path) == report
    assert storage.list_followup_experiments(other_run, path) == []
    outcome_activity = storage.load_research(run_id, path)["activity"][0]
    assert outcome_activity["kind"] == "followup_outcome"
    assert outcome_activity["detail"]["experiment_id"] == first["id"]
    assert outcome_activity["detail"]["previous_status"] == previous["status"]
