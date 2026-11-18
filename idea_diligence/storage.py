"""Immutable analysis snapshots and their local founder decision records."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .decision import EVIDENCE_VERDICTS, OUTCOME_DECISIONS, OUTCOME_STATUSES
from .local_analysis import _founder_experiment

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, title TEXT NOT NULL,
    mode TEXT NOT NULL, report TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence_reviews (
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    assumption_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('accept', 'question', 'exclude')),
    note TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, assumption_id, source_id)
);
CREATE TABLE IF NOT EXISTS experiment_outcomes (
    run_id INTEGER PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    assumption_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('planned', 'running', 'completed')),
    participants INTEGER,
    qualifying INTEGER,
    notes TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('undecided', 'continue', 'revise', 'stop')),
    updated_at TEXT NOT NULL,
    CHECK ((participants IS NULL AND qualifying IS NULL) OR
           (participants IS NOT NULL AND qualifying IS NOT NULL AND
            participants >= 0 AND qualifying >= 0 AND qualifying <= participants))
);
CREATE TABLE IF NOT EXISTS experiment_plans (
    run_id INTEGER PRIMARY KEY REFERENCES runs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    plan TEXT NOT NULL
);
"""


def database_path() -> Path:
    default = Path(__file__).resolve().parents[1] / ".local" / "runs.sqlite3"
    return Path(os.environ.get("IDEA_DILIGENCE_DB", default)).expanduser()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.executescript(SCHEMA)
    except sqlite3.Error:
        db.close()
        raise
    return db


def save_run(report: dict, path: Path | None = None) -> int:
    with closing(connect(path or database_path())) as db, db:
        cursor = db.execute(
            "INSERT INTO runs (created_at, title, mode, report) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), report["brief"]["title"],
             report["mode"], json.dumps(report, ensure_ascii=False)),
        )
        return int(cursor.lastrowid)


def recent_runs(path: Path | None = None) -> list[tuple]:
    with closing(connect(path or database_path())) as db:
        return db.execute(
            "SELECT id, created_at, title, mode FROM runs ORDER BY id DESC LIMIT 30"
        ).fetchall()


def load_run(run_id: int, path: Path | None = None) -> dict | None:
    with closing(connect(path or database_path())) as db:
        row = db.execute("SELECT report FROM runs WHERE id = ?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def load_workspace(run_id: int, path: Path | None = None) -> dict:
    """Read the run's evidence reviews, later plan and outcome in one snapshot."""
    with closing(connect(path or database_path())) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        reviews = db.execute(
            """SELECT assumption_id, source_id, verdict, note, updated_at
               FROM evidence_reviews WHERE run_id = ? ORDER BY assumption_id, source_id""",
            (run_id,),
        ).fetchall()
        outcome = db.execute(
            """SELECT assumption_id, status, participants, qualifying, notes, decision, updated_at
               FROM experiment_outcomes WHERE run_id = ?""",
            (run_id,),
        ).fetchone()
        plan = _load_founder_plan(db, run_id)
    return {"reviews": [dict(row) for row in reviews], "outcome": dict(outcome) if outcome else None,
            "plan": plan}


def _require_report(db: sqlite3.Connection, run_id: int) -> dict:
    row = db.execute("SELECT report FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise ValueError("This analysis must be saved before adding a review, plan, or outcome.")
    return json.loads(row[0])


def _load_founder_plan(db: sqlite3.Connection, run_id: int) -> dict | None:
    row = db.execute("SELECT plan FROM experiment_plans WHERE run_id = ?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def save_founder_plan(run_id: int, plan: dict, path: Path | None = None) -> dict:
    """Attach a single founder-authored experiment to a run that had none."""
    with closing(connect(path or database_path())) as db, db:
        report = _require_report(db, run_id)
        if report.get("experiment"):
            raise ValueError("This analysis already has an experiment plan.")
        assumptions = report.get("assumptions", [])
        if not assumptions:
            raise ValueError("This analysis needs an assumption before you add an experiment.")
        normalized = _founder_experiment(plan, assumptions)
        if normalized is None:
            raise ValueError("Enter the experiment plan before saving.")
        saved = db.execute(
            """INSERT INTO experiment_plans (run_id, created_at, plan)
               VALUES (?, ?, ?) ON CONFLICT (run_id) DO NOTHING""",
            (run_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
             json.dumps(normalized, ensure_ascii=False)),
        )
        if not saved.rowcount:
            raise ValueError("This analysis already has an experiment plan.")
    return normalized


def _note(value: str, limit: int) -> str:
    if not isinstance(value, str) or len(value.strip()) > limit:
        raise ValueError(f"Use at most {limit:,} characters of text for your note.")
    return value.strip()


def save_evidence_review(
    run_id: int, assumption_id: str, source_id: str, verdict: str, note: str = "",
    path: Path | None = None,
) -> dict:
    """Save a human judgment about this source's link to this assumption."""
    if verdict not in EVIDENCE_VERDICTS:
        raise ValueError("Choose Accept, Question, or Exclude.")
    record = {
        "assumption_id": assumption_id,
        "source_id": source_id,
        "verdict": verdict,
        "note": _note(note, 2_000),
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    with closing(connect(path or database_path())) as db, db:
        report = _require_report(db, run_id)
        if not any(
            row["assumption_id"] == assumption_id and row["source_id"] == source_id
            for row in report.get("links", [])
        ):
            raise ValueError("This evidence link does not belong to the saved analysis.")
        db.execute(
            """INSERT INTO evidence_reviews
               (run_id, assumption_id, source_id, verdict, note, updated_at)
               VALUES (:run_id, :assumption_id, :source_id, :verdict, :note, :updated_at)
               ON CONFLICT (run_id, assumption_id, source_id) DO UPDATE SET
               verdict = excluded.verdict, note = excluded.note, updated_at = excluded.updated_at""",
            {"run_id": run_id, **record},
        )
    return record


def save_experiment_outcome(
    run_id: int, status: str, participants: int | None, qualifying: int | None, notes: str = "",
    decision: str = "undecided", path: Path | None = None,
) -> dict:
    """Record observed results and a founder's decision against the saved test."""
    if status not in OUTCOME_STATUSES or decision not in OUTCOME_DECISIONS:
        raise ValueError("Choose a valid experiment status and decision.")
    if (participants, qualifying) != (None, None) and (
        type(participants) is not int or type(qualifying) is not int
        or not 0 <= qualifying <= participants < (1 << 63)
    ):
        raise ValueError("Enter both counts and use whole numbers. Qualifying outcomes cannot exceed total observations.")
    notes = _note(notes, 4_000)
    if status == "completed" and participants is None and not notes:
        raise ValueError("Record the counts or describe the observed outcome before marking the test complete.")
    with closing(connect(path or database_path())) as db, db:
        report = _require_report(db, run_id)
        experiment = report.get("experiment") or _load_founder_plan(db, run_id)
        if not experiment:
            raise ValueError("This analysis does not have an experiment to track.")
        record = {
            "assumption_id": experiment["assumption_id"],
            "status": status,
            "participants": participants,
            "qualifying": qualifying,
            "notes": notes,
            "decision": decision,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        db.execute(
            """INSERT INTO experiment_outcomes
               (run_id, assumption_id, status, participants, qualifying, notes, decision, updated_at)
               VALUES (:run_id, :assumption_id, :status, :participants, :qualifying, :notes, :decision, :updated_at)
               ON CONFLICT (run_id) DO UPDATE SET status = excluded.status,
               participants = excluded.participants, qualifying = excluded.qualifying,
               notes = excluded.notes, decision = excluded.decision, updated_at = excluded.updated_at""",
            {"run_id": run_id, **record},
        )
    return record
