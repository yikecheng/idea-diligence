"""Recorded risk judgments and a reproducible current priority."""

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path

from .decision import effective_assumptions
from .storage import connect, database_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS priority_updates (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    assumption_id TEXT NOT NULL,
    impact INTEGER NOT NULL CHECK (impact BETWEEN 1 AND 5),
    uncertainty INTEGER NOT NULL CHECK (uncertainty BETWEEN 1 AND 5),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS priority_study ON priority_updates(run_id, id);
"""

MAX_UPDATES = 200
UNRESOLVED = frozenset({"open", "context", "mixed"})


def load_priority_updates(run_id: int, path: Path | None = None) -> list[dict]:
    with closing(connect(path or database_path())) as db:
        db.executescript(SCHEMA)
        rows = db.execute(
            "SELECT id, assumption_id, impact, uncertainty, reason, created_at "
            "FROM priority_updates WHERE run_id = ? ORDER BY id", (run_id,),
        ).fetchall()
    keys = ("id", "assumption_id", "impact", "uncertainty", "reason", "created_at")
    return [dict(zip(keys, row)) for row in rows]


def save_priority_update(
    run_id: int, assumption_id: str, impact: int, uncertainty: int, reason: str,
    path: Path | None = None,
) -> dict:
    if (type(impact) is not int or type(uncertainty) is not int
            or not 1 <= impact <= 5 or not 1 <= uncertainty <= 5):
        raise ValueError("Impact and uncertainty each need a score from 1 to 5.")
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason or len(reason) > 500:
        raise ValueError("Explain what changed in 1–500 characters.")
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(connect(path or database_path())) as db, db:
        db.executescript(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        snapshot = db.execute("SELECT report FROM runs WHERE id = ?", (run_id,)).fetchone()
        report = json.loads(snapshot[0]) if snapshot else {}
        assumption = next((row for row in report.get("assumptions", []) if row["id"] == assumption_id), None)
        if not assumption:
            raise ValueError("Choose an assumption in this saved analysis.")
        count = db.execute("SELECT COUNT(*) FROM priority_updates WHERE run_id = ?", (run_id,)).fetchone()[0]
        if count >= MAX_UPDATES:
            raise ValueError("This analysis has reached its priority history limit.")
        before = db.execute(
            "SELECT impact, uncertainty FROM priority_updates WHERE run_id = ? AND assumption_id = ? ORDER BY id DESC LIMIT 1",
            (run_id, assumption_id),
        ).fetchone() or (assumption["impact"], assumption["uncertainty"])
        if (impact, uncertainty) == before:
            raise ValueError("Change a score before recording a new priority update.")
        row = db.execute(
            "INSERT INTO priority_updates (run_id, assumption_id, impact, uncertainty, reason, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)", (run_id, assumption_id, impact, uncertainty, reason, created_at),
        )
        update_id = row.lastrowid
    return {"id": update_id, "assumption_id": assumption_id, "impact": impact, "uncertainty": uncertainty,
            "reason": reason, "created_at": created_at}


def current_assumptions(report: dict, reviews: list[dict], updates: list[dict]) -> list[dict]:
    latest = {update["assumption_id"]: update for update in updates}
    reviewed_links = {(review["assumption_id"], review["source_id"]) for review in reviews}
    pending_assumptions = {
        link["assumption_id"] for link in report.get("links", [])
        if link.get("proposed_stance") and (link["assumption_id"], link["source_id"]) not in reviewed_links
    }
    ranked = []
    for row in effective_assumptions(report, reviews):
        update = latest.get(row["id"])
        current_impact = update["impact"] if update else row["impact"]
        current_uncertainty = update["uncertainty"] if update else row["uncertainty"]
        current_status = row["status"]
        if row["reviewed_status"] is not None and not row["unreviewed_count"]:
            current_status = row["reviewed_status"]
        ranked.append({**row, "current_impact": current_impact, "current_uncertainty": current_uncertainty,
                       "current_risk": current_impact * current_uncertainty, "current_status": current_status,
                       "priority_update": update, "pending_addition": row["id"] in pending_assumptions})
    return sorted(ranked, key=lambda row: (-row["current_risk"], -row["current_impact"],
                                          -row["current_uncertainty"], row["id"]))


def next_priority(rows: list[dict]) -> dict | None:
    return next((row for row in rows if row["current_status"] in UNRESOLVED
                 or row["pending_addition"] or row["questioned_count"]), None)
