"""Persistence and interpretation checks for a founder's review and decision."""

import sqlite3

import pytest

from idea_diligence.decision import effective_assumptions
from idea_diligence.engine import load_demo_brief, run_analysis
from idea_diligence.storage import (
    load_run,
    load_workspace,
    recent_runs,
    save_evidence_review,
    save_experiment_outcome,
    save_run,
)


@pytest.fixture
def record(tmp_path):
    path = tmp_path / "prior-version.sqlite3"
    # Recreate the only table shipped in the midpoint app to test in-place migration.
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE runs (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, "
            "title TEXT NOT NULL, mode TEXT NOT NULL, report TEXT NOT NULL)"
        )
    report = run_analysis(load_demo_brief(), "demo")
    run_id = save_run(report, path)
    return path, run_id, report


def test_review_persists_without_changing_machine_report(record):
    path, run_id, report = record
    assert load_workspace(run_id, path) == {"reviews": [], "outcome": None, "plan": None}
    assert recent_runs(path)[0][0] == run_id
    link = report["links"][0]
    assumption_id, source_id = link["assumption_id"], link["source_id"]
    save_evidence_review(run_id, assumption_id, source_id, "question", "Can this result generalize?", path)
    [review] = load_workspace(run_id, path)["reviews"]
    assert review["verdict"] == "question"
    [assumption] = [a for a in effective_assumptions(report, [review]) if a["id"] == assumption_id]
    assert assumption["reviewed_status"] == "open"
    assert assumption["questioned_count"] == 1
    assert assumption["unreviewed_count"] == 2

    replacement = save_evidence_review(run_id, assumption_id, source_id, "accept", "Public product claim", path)
    assert load_workspace(run_id, path)["reviews"] == [replacement]
    [assumption] = [a for a in effective_assumptions(report, [replacement]) if a["id"] == assumption_id]
    assert assumption["reviewed_status"] == "challenged"
    assert assumption["accepted_count"] == 1
    assert load_run(run_id, path) == report


def test_outcome_updates_are_per_run(record):
    path, run_id, report = record
    other_run = save_run(report, path)
    save_experiment_outcome(run_id, "running", None, None, "Recruiting", path=path)
    result = save_experiment_outcome(run_id, "completed", 8, 3, "Three came back", "revise", path)
    assert result["assumption_id"] == report["experiment"]["assumption_id"]
    assert result["participants"] == 8
    assert result["qualifying"] == 3
    assert load_workspace(run_id, path)["outcome"] == result
    assert load_workspace(other_run, path)["outcome"] is None
    assert load_run(run_id, path) == report


def test_rejects_invalid_links_and_incomplete_or_impossible_outcomes(record):
    path, run_id, report = record
    with pytest.raises(ValueError, match="does not belong"):
        save_evidence_review(run_id, "A1", "S999", "exclude", path=path)
    with pytest.raises(ValueError, match="cannot exceed"):
        save_experiment_outcome(run_id, "completed", 3, 5, path=path)
    with pytest.raises(ValueError, match="Record the counts"):
        save_experiment_outcome(run_id, "completed", None, None, path=path)
    with pytest.raises(ValueError, match="no\b|does not have"):
        partial = save_run({**report, "status": "partial", "experiment": None}, path)
        save_experiment_outcome(partial, "planned", None, None, path=path)
    assert load_workspace(run_id, path) == {"reviews": [], "outcome": None, "plan": None}
