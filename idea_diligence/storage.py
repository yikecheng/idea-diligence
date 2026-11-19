"""Immutable analysis snapshots and their local founder research and decisions."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .decision import EVIDENCE_VERDICTS, OUTCOME_DECISIONS, OUTCOME_STATUSES
from .engine import STANCES, _source_identity, _source_url, _space_normalized
from .local_analysis import _discussion_sources, _founder_experiment, _value
from .public_search import MAX_HITS, _clean_query

MAX_RESEARCH_ROUNDS = 20
MAX_FOUNDER_SOURCES = 30
MAX_FOUNDER_LINKS = 50
MAX_FOLLOWUP_EXPERIMENTS = 20

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
CREATE TABLE IF NOT EXISTS research_sources (
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    identity TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('discussion_lead', 'founder_supplied')),
    source TEXT NOT NULL,
    PRIMARY KEY (run_id, source_id),
    UNIQUE (run_id, kind, identity)
);
CREATE TABLE IF NOT EXISTS research_links (
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    assumption_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    proposed_stance TEXT NOT NULL CHECK (proposed_stance IN ('supports', 'challenges', 'context')),
    reason TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (run_id, assumption_id, source_id)
);
CREATE TABLE IF NOT EXISTS research_rounds (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    created_at TEXT NOT NULL,
    added_count INTEGER NOT NULL,
    results TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS research_rounds_run ON research_rounds (run_id, id);
CREATE TABLE IF NOT EXISTS workspace_activity (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS workspace_activity_run ON workspace_activity (run_id, id);
CREATE TABLE IF NOT EXISTS followup_experiments (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    plan TEXT NOT NULL,
    outcome TEXT,
    UNIQUE (run_id, plan)
);
CREATE INDEX IF NOT EXISTS followup_experiments_run ON followup_experiments (run_id, id);
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
            (_now(), report["brief"]["title"],
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
        raise ValueError("Save this analysis before adding to its workspace.")
    return json.loads(row[0])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _record_activity(db: sqlite3.Connection, run_id: int, kind: str, at: str, detail: dict) -> None:
    db.execute(
        "INSERT INTO workspace_activity (run_id, kind, created_at, detail) VALUES (?, ?, ?, ?)",
        (run_id, kind, at, json.dumps(detail, ensure_ascii=False)),
    )


def _research_round(row: dict) -> dict:
    results = json.loads(row["results"])
    return {**row, "results": results, "result_count": len(results), "source_ids": [source["id"] for source in results]}


def load_research(run_id: int, path: Path | None = None) -> dict:
    """Read additions to the saved analysis, with newest rounds and activity first."""
    with closing(connect(path or database_path())) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        sources = db.execute(
            "SELECT source FROM research_sources WHERE run_id = ? ORDER BY rowid", (run_id,),
        ).fetchall()
        links = db.execute(
            """SELECT assumption_id, source_id, 'context' AS stance, proposed_stance, reason, added_at
               FROM research_links WHERE run_id = ? ORDER BY rowid""", (run_id,),
        ).fetchall()
        rounds = db.execute(
            """SELECT id, query, created_at, added_count, results FROM research_rounds
               WHERE run_id = ? ORDER BY id DESC""", (run_id,),
        ).fetchall()
        activity = db.execute(
            """SELECT id, kind, created_at, detail FROM workspace_activity
               WHERE run_id = ? ORDER BY id DESC LIMIT 50""", (run_id,),
        ).fetchall()
    return {
        "sources": [json.loads(row["source"]) for row in sources],
        "links": [dict(row) for row in links],
        "rounds": [_research_round(dict(row)) for row in rounds],
        "activity": [{**dict(row), "detail": json.loads(row["detail"])} for row in activity],
    }


def _stored_sources(db: sqlite3.Connection, run_id: int, kind: str) -> dict[str, dict]:
    rows = db.execute(
        "SELECT identity, source FROM research_sources WHERE run_id = ? AND kind = ?", (run_id, kind),
    )
    return {identity: json.loads(source) for identity, source in rows}


def _insert_source(db: sqlite3.Connection, run_id: int, identity: str, source: dict) -> None:
    db.execute(
        "INSERT INTO research_sources (run_id, source_id, identity, kind, source) VALUES (?, ?, ?, ?, ?)",
        (run_id, source["id"], identity, source["kind"], json.dumps(source, ensure_ascii=False)),
    )


def append_research_round(run_id: int, query: str, leads: list[dict], path: Path | None = None) -> dict:
    """Record a completed public search and preserve its result list even when it adds no leads."""
    query = _clean_query(query)
    if not isinstance(leads, (list, tuple)) or len(leads) > MAX_HITS:
        raise ValueError(f"A completed search can contain up to {MAX_HITS} discussion leads.")
    created_at = _now()
    leads = _discussion_sources(leads, 0, created_at[:10])
    with closing(connect(path or database_path())) as db, db:
        db.execute("BEGIN IMMEDIATE")
        report = _require_report(db, run_id)
        count = db.execute("SELECT COUNT(*) FROM research_rounds WHERE run_id = ?", (run_id,)).fetchone()[0]
        if count >= MAX_RESEARCH_ROUNDS:
            raise ValueError(f"This analysis already has {MAX_RESEARCH_ROUNDS} public search rounds.")
        known = {
            _source_identity(source["url"]): source["id"] for source in report.get("sources", [])
            if source.get("url") and source.get("kind") != "founder_supplied"
        }
        saved = _stored_sources(db, run_id, "discussion_lead")
        known.update({identity: source["id"] for identity, source in saved.items()})
        results = []
        seen = set()
        added_count = 0
        for lead in leads:
            identity = _source_identity(lead["url"])
            if identity in seen:
                continue
            seen.add(identity)
            if identity not in known:
                added_count += 1
                known[identity] = f"R{len(saved) + added_count}"
                _insert_source(db, run_id, identity, {**lead, "id": known[identity]})
            results.append({**lead, "id": known[identity]})
        cursor = db.execute(
            "INSERT INTO research_rounds (run_id, query, created_at, added_count, results) VALUES (?, ?, ?, ?, ?)",
            (run_id, query, created_at, added_count, json.dumps(results, ensure_ascii=False)),
        )
        round_id = int(cursor.lastrowid)
        _record_activity(db, run_id, "research_round", created_at,
                         {"round_id": round_id, "result_count": len(results), "added_count": added_count})
    return {
        "id": round_id, "query": query, "created_at": created_at, "added_count": added_count,
        "results": results, "result_count": len(results), "source_ids": [lead["id"] for lead in results],
    }


def _excerpt_identity(url: str, passage: str) -> str:
    return json.dumps([_source_identity(url), _space_normalized(passage)], ensure_ascii=False)


def add_founder_evidence(
    run_id: int, assumption_id: str, title: str, url: str, passage: str, stance: str,
    reason: str = "", path: Path | None = None,
) -> dict:
    """Attach an unverified founder excerpt and keep their proposed relationship separate."""
    title = _value(title, "Excerpt title", 160)
    url = _source_url(_value(url, "Excerpt URL", 2_000))
    passage = _value(passage, "Excerpt passage", 1_200)
    stance = _value(stance, "Excerpt relationship", 30).lower()
    reason = _value(reason, "Excerpt note", 350, required=False)
    if not url:
        raise ValueError("Enter a public HTTP or HTTPS source URL.")
    if stance not in STANCES:
        raise ValueError("Choose Supports, Challenges, or Context for the proposed relationship.")
    identity = _excerpt_identity(url, passage)
    with closing(connect(path or database_path())) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.row_factory = sqlite3.Row
        report = _require_report(db, run_id)
        if not any(row["id"] == assumption_id for row in report.get("assumptions", [])):
            raise ValueError("Choose an assumption from this saved analysis.")
        saved = _stored_sources(db, run_id, "founder_supplied")
        source = saved.get(identity) or next((
            row for row in report.get("sources", []) if row.get("kind") == "founder_supplied"
            and _excerpt_identity(row["url"], row["passage"]) == identity
        ), None)
        created_at = _now()
        if source is None:
            if len(saved) >= MAX_FOUNDER_SOURCES:
                raise ValueError(f"This analysis already has {MAX_FOUNDER_SOURCES} added founder excerpts.")
            source = {"id": f"FS{len(saved) + 1}", "title": title, "url": url, "passage": passage,
                      "kind": "founder_supplied", "retrieved_at": created_at[:10]}
            _insert_source(db, run_id, identity, source)
        if any(row["assumption_id"] == assumption_id and row["source_id"] == source["id"]
               for row in report.get("links", [])):
            raise ValueError("This excerpt already appears on that assumption in the original analysis.")
        prior = db.execute(
            """SELECT assumption_id, source_id, 'context' AS stance, proposed_stance, reason, added_at
               FROM research_links WHERE run_id = ? AND assumption_id = ? AND source_id = ?""",
            (run_id, assumption_id, source["id"]),
        ).fetchone()
        if prior:
            return {"source": source, "link": dict(prior), "added": False}
        count = db.execute("SELECT COUNT(*) FROM research_links WHERE run_id = ?", (run_id,)).fetchone()[0]
        if count >= MAX_FOUNDER_LINKS:
            raise ValueError(f"This analysis already has {MAX_FOUNDER_LINKS} added evidence links.")
        link = {"assumption_id": assumption_id, "source_id": source["id"], "stance": "context",
                "proposed_stance": stance, "reason": reason, "added_at": created_at}
        db.execute(
            """INSERT INTO research_links (run_id, assumption_id, source_id, proposed_stance, reason, added_at)
               VALUES (:run_id, :assumption_id, :source_id, :proposed_stance, :reason, :added_at)""",
            {"run_id": run_id, **link},
        )
        _record_activity(db, run_id, "founder_evidence", created_at,
                         {"assumption_id": assumption_id, "source_id": source["id"], "proposed_stance": stance})
    return {"source": source, "link": link, "added": True}


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
        created_at = _now()
        saved = db.execute(
            """INSERT INTO experiment_plans (run_id, created_at, plan)
               VALUES (?, ?, ?) ON CONFLICT (run_id) DO NOTHING""",
            (run_id, created_at, json.dumps(normalized, ensure_ascii=False)),
        )
        if not saved.rowcount:
            raise ValueError("This analysis already has an experiment plan.")
        _record_activity(db, run_id, "founder_plan", created_at, {"assumption_id": normalized["assumption_id"]})
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
    }
    with closing(connect(path or database_path())) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.row_factory = sqlite3.Row
        report = _require_report(db, run_id)
        if not any(
            row["assumption_id"] == assumption_id and row["source_id"] == source_id
            for row in report.get("links", [])
        ) and db.execute(
            "SELECT 1 FROM research_links WHERE run_id = ? AND assumption_id = ? AND source_id = ?",
            (run_id, assumption_id, source_id),
        ).fetchone() is None:
            raise ValueError("This evidence link does not belong to the saved analysis.")
        previous = db.execute(
            """SELECT assumption_id, source_id, verdict, note, updated_at FROM evidence_reviews
               WHERE run_id = ? AND assumption_id = ? AND source_id = ?""",
            (run_id, assumption_id, source_id),
        ).fetchone()
        if previous and all(previous[key] == value for key, value in record.items()):
            return dict(previous)
        record["updated_at"] = _now()
        db.execute(
            """INSERT INTO evidence_reviews
               (run_id, assumption_id, source_id, verdict, note, updated_at)
               VALUES (:run_id, :assumption_id, :source_id, :verdict, :note, :updated_at)
               ON CONFLICT (run_id, assumption_id, source_id) DO UPDATE SET
               verdict = excluded.verdict, note = excluded.note, updated_at = excluded.updated_at""",
            {"run_id": run_id, **record},
        )
        _record_activity(db, run_id, "evidence_review", record["updated_at"], {
            "assumption_id": assumption_id, "source_id": source_id, "verdict": verdict,
            "previous_verdict": previous["verdict"] if previous else None,
        })
    return record


def _outcome_values(status: str, participants: int | None, qualifying: int | None, notes: str, decision: str) -> dict:
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
    return {"status": status, "participants": participants, "qualifying": qualifying, "notes": notes,
            "decision": decision}


def _outcome_detail(record: dict, previous: sqlite3.Row | dict | None) -> dict:
    details = {key: record[key] for key in ("assumption_id", "status", "decision", "participants", "qualifying")}
    return {**details, "previous_status": previous["status"] if previous else None,
            "previous_decision": previous["decision"] if previous else None}


def save_experiment_outcome(
    run_id: int, status: str, participants: int | None, qualifying: int | None, notes: str = "",
    decision: str = "undecided", path: Path | None = None,
) -> dict:
    """Record observed results and a founder's decision against the saved test."""
    values = _outcome_values(status, participants, qualifying, notes, decision)
    with closing(connect(path or database_path())) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.row_factory = sqlite3.Row
        report = _require_report(db, run_id)
        experiment = report.get("experiment") or _load_founder_plan(db, run_id)
        if not experiment:
            raise ValueError("This analysis does not have an experiment to track.")
        record = {"assumption_id": experiment["assumption_id"], **values}
        previous = db.execute(
            """SELECT assumption_id, status, participants, qualifying, notes, decision, updated_at
               FROM experiment_outcomes WHERE run_id = ?""", (run_id,),
        ).fetchone()
        if previous and all(previous[key] == value for key, value in record.items()):
            return dict(previous)
        record["updated_at"] = _now()
        db.execute(
            """INSERT INTO experiment_outcomes
               (run_id, assumption_id, status, participants, qualifying, notes, decision, updated_at)
               VALUES (:run_id, :assumption_id, :status, :participants, :qualifying, :notes, :decision, :updated_at)
               ON CONFLICT (run_id) DO UPDATE SET status = excluded.status,
               participants = excluded.participants, qualifying = excluded.qualifying,
               notes = excluded.notes, decision = excluded.decision, updated_at = excluded.updated_at""",
            {"run_id": run_id, **record},
        )
        _record_activity(db, run_id, "experiment_outcome", record["updated_at"], _outcome_detail(record, previous))
    return record


def list_followup_experiments(run_id: int, path: Path | None = None) -> list[dict]:
    """Return founder-authored follow-up experiments and their current outcomes, newest first."""
    with closing(connect(path or database_path())) as db:
        rows = db.execute(
            "SELECT id, created_at, plan, outcome FROM followup_experiments WHERE run_id = ? ORDER BY id DESC",
            (run_id,),
        ).fetchall()
    return [{"id": item_id, "created_at": created_at, "plan": json.loads(plan),
             "outcome": json.loads(outcome) if outcome else None} for item_id, created_at, plan, outcome in rows]


def save_followup_experiment(run_id: int, plan: dict, path: Path | None = None) -> dict:
    """Add an independently tracked follow-up with a fixed decision threshold."""
    with closing(connect(path or database_path())) as db, db:
        db.execute("BEGIN IMMEDIATE")
        assumptions = _require_report(db, run_id).get("assumptions", [])
        if not assumptions:
            raise ValueError("This analysis needs an assumption before you add a follow-up experiment.")
        normalized = _founder_experiment(plan, assumptions)
        if normalized is None:
            raise ValueError("Enter the follow-up plan before saving.")
        count = db.execute("SELECT COUNT(*) FROM followup_experiments WHERE run_id = ?", (run_id,)).fetchone()[0]
        if count >= MAX_FOLLOWUP_EXPERIMENTS:
            raise ValueError(f"This analysis already has {MAX_FOLLOWUP_EXPERIMENTS} follow-up experiments.")
        created_at = _now()
        cursor = db.execute(
            """INSERT INTO followup_experiments (run_id, created_at, plan) VALUES (?, ?, ?)
               ON CONFLICT (run_id, plan) DO NOTHING""",
            (run_id, created_at, json.dumps(normalized, ensure_ascii=False)),
        )
        if not cursor.rowcount:
            raise ValueError("An identical follow-up already exists. Describe what is different about this trial.")
        experiment_id = int(cursor.lastrowid)
        _record_activity(db, run_id, "followup_plan", created_at,
                         {"assumption_id": normalized["assumption_id"], "experiment_id": experiment_id})
    return {"id": experiment_id, "created_at": created_at, "plan": normalized, "outcome": None}


def save_followup_outcome(
    run_id: int, experiment_id: int, status: str, participants: int | None, qualifying: int | None, notes: str = "",
    decision: str = "undecided", path: Path | None = None,
) -> dict:
    """Record observations against the selected follow-up and preserve the original plan."""
    values = _outcome_values(status, participants, qualifying, notes, decision)
    with closing(connect(path or database_path())) as db, db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT plan, outcome FROM followup_experiments WHERE run_id = ? AND id = ?", (run_id, experiment_id),
        ).fetchone()
        if row is None:
            raise ValueError("This follow-up experiment does not belong to the saved analysis.")
        plan = json.loads(row[0])
        previous = json.loads(row[1]) if row[1] else None
        record = {"assumption_id": plan["assumption_id"], **values}
        if previous and all(previous[key] == value for key, value in record.items()):
            return previous
        record["updated_at"] = _now()
        db.execute(
            "UPDATE followup_experiments SET outcome = ? WHERE run_id = ? AND id = ?",
            (json.dumps(record, ensure_ascii=False), run_id, experiment_id),
        )
        _record_activity(db, run_id, "followup_outcome", record["updated_at"],
                         {"experiment_id": experiment_id, **_outcome_detail(record, previous)})
    return record
