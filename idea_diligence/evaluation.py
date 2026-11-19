"""Frozen evaluation cases, blinded packets, and human judgments."""

import random
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .storage import connect, database_path

CONDITIONS = {
    "direct_ai": "Standard AI prompt",
    "competitor_report": "Static competitor report",
    "idea_diligence": "Idea Diligence",
}
LABELS = ("A", "B", "C")
RUBRIC_VERSION = 1
RUBRIC = {
    "new_risk": ("Overlooked critical risk", "A risk missing from the frozen brief could change the decision and follows from traceable evidence."),
    "grounding": ("Source grounding", "Traceable sources support the consequential claims, with inference marked."),
    "decision": ("Decision targeted", "The experiment tests a named high-risk assumption and informs a decision."),
    "measure": ("Observable outcome", "A second person could tell what to measure and how to measure it."),
    "threshold": ("Decision threshold", "Results map to a stated pass, fail, or inconclusive action."),
    "feasibility": ("Feasibility", "The time, participants, and materials fit a small, realistic test."),
    "interpretation": ("Interpretation", "The experiment addresses plausible alternative explanations and open questions."),
}
EXPERIMENT_CRITERIA = ("decision", "measure", "threshold", "feasibility", "interpretation")
SCORE_LABELS = {0: "0 · Missing or unsupported", 1: "1 · Partial", 2: "2 · Specific and defensible"}
LIMITATIONS = (
    "These scores are human judgments about outputs under the recorded conditions. "
    "Experiment scores measure the design. Observed outcomes require running the experiment. "
    "Preference and self-reported novelty are separate founder judgments. "
    "Matching and masking rely on the organizer."
)
CASE_FIELDS = {
    "title": ("Case title", 100),
    "brief": ("Idea and target customer", 2_500),
    "known_alternatives": ("Known alternatives", 2_500),
    "known_assumptions": ("Known beliefs and planned test", 2_500),
    "budget": ("Research budget", 1_000),
    "source_scope": ("Available sources", 2_000),
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS evaluation_cases (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    brief TEXT NOT NULL,
    known_alternatives TEXT NOT NULL,
    known_assumptions TEXT NOT NULL,
    budget TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    required_reviews INTEGER NOT NULL CHECK (required_reviews BETWEEN 1 AND 3),
    packet_ready_at TEXT
);
CREATE TABLE IF NOT EXISTS evaluation_outputs (
    case_id INTEGER NOT NULL REFERENCES evaluation_cases(id) ON DELETE CASCADE,
    label TEXT NOT NULL CHECK (label IN ('A', 'B', 'C')),
    condition TEXT NOT NULL CHECK (condition IN ('direct_ai', 'competitor_report', 'idea_diligence')),
    content TEXT NOT NULL,
    PRIMARY KEY (case_id, label),
    UNIQUE (case_id, condition)
);
CREATE TABLE IF NOT EXISTS evaluation_reviews (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES evaluation_cases(id) ON DELETE CASCADE,
    reviewer TEXT NOT NULL,
    reviewer_key TEXT NOT NULL,
    rubric_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (case_id, reviewer_key)
);
CREATE TABLE IF NOT EXISTS evaluation_scores (
    review_id INTEGER NOT NULL REFERENCES evaluation_reviews(id) ON DELETE CASCADE,
    label TEXT NOT NULL CHECK (label IN ('A', 'B', 'C')),
    criterion TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 2),
    PRIMARY KEY (review_id, label, criterion)
);
CREATE TABLE IF NOT EXISTS evaluation_review_notes (
    review_id INTEGER NOT NULL REFERENCES evaluation_reviews(id) ON DELETE CASCADE,
    label TEXT NOT NULL CHECK (label IN ('A', 'B', 'C')),
    note TEXT NOT NULL,
    PRIMARY KEY (review_id, label)
);
CREATE TABLE IF NOT EXISTS evaluation_founder_feedback (
    case_id INTEGER PRIMARY KEY REFERENCES evaluation_cases(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    preference TEXT NOT NULL CHECK (preference IN ('A', 'B', 'C', 'tie'))
);
CREATE TABLE IF NOT EXISTS evaluation_founder_novelty (
    case_id INTEGER NOT NULL REFERENCES evaluation_founder_feedback(case_id) ON DELETE CASCADE,
    label TEXT NOT NULL CHECK (label IN ('A', 'B', 'C')),
    competitor TEXT NOT NULL,
    risk TEXT NOT NULL,
    PRIMARY KEY (case_id, label)
);
"""


def _connect(path: Path | None) -> sqlite3.Connection:
    db = connect(path or database_path())
    try:
        db.row_factory = sqlite3.Row
        db.executescript(SCHEMA)
    except sqlite3.Error:
        db.close()
        raise
    return db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _text(value: str, label: str, limit: int, required: bool = True) -> str:
    value = value.strip() if isinstance(value, str) else ""
    if required and not value:
        raise ValueError(f"Enter {label.lower()}.")
    if len(value) > limit:
        raise ValueError(f"Use at most {limit:,} characters for {label.lower()}.")
    return value


def create_case(fields: dict[str, str], path: Path | None = None, *, required_reviews: int = 1) -> int:
    """Freeze the brief and comparison conditions before accepting any outputs."""
    values = {key: _text(fields.get(key), label, limit) for key, (label, limit) in CASE_FIELDS.items()}
    if type(required_reviews) is not int or required_reviews not in (1, 2, 3):
        raise ValueError("Register one to three independent reviewers.")
    with closing(_connect(path)) as db, db:
        case = db.execute(
            """INSERT INTO evaluation_cases
               (created_at, title, brief, known_alternatives, known_assumptions, budget, source_scope, required_reviews)
               VALUES (:created_at, :title, :brief, :known_alternatives, :known_assumptions, :budget, :source_scope,
                       :required_reviews)""",
            {"created_at": _now(), "required_reviews": required_reviews, **values},
        )
        return int(case.lastrowid)


def list_cases(path: Path | None = None) -> list[dict]:
    with closing(_connect(path)) as db:
        return [dict(row) for row in db.execute(
            "SELECT id, title, packet_ready_at FROM evaluation_cases ORDER BY id DESC"
        )]


def get_case(case_id: int, path: Path | None = None) -> dict | None:
    with closing(_connect(path)) as db:
        row = db.execute("SELECT * FROM evaluation_cases WHERE id = ?", (case_id,)).fetchone()
        return dict(row) if row else None


def attach_outputs(case_id: int, outputs: dict[str, str], path: Path | None = None) -> None:
    if outputs.keys() != CONDITIONS.keys():
        raise ValueError("Provide one output from each comparison condition.")
    clean = {key: _text(value, CONDITIONS[key], 16_000) for key, value in outputs.items()}
    if len({" ".join(value.split()) for value in clean.values()}) != len(CONDITIONS):
        raise ValueError("Each comparison condition needs a distinct output.")
    shuffled = list(clean.items())
    random.SystemRandom().shuffle(shuffled)
    with closing(_connect(path)) as db, db:
        updated = db.execute(
            "UPDATE evaluation_cases SET packet_ready_at = ? WHERE id = ? AND packet_ready_at IS NULL",
            (_now(), case_id),
        )
        if not updated.rowcount:
            raise ValueError("Choose a frozen case that is still awaiting outputs.")
        db.executemany(
            "INSERT INTO evaluation_outputs (case_id, label, condition, content) VALUES (?, ?, ?, ?)",
            ((case_id, label, condition, content) for label, (condition, content) in zip(LABELS, shuffled)),
        )


def get_blind_packet(case_id: int, path: Path | None = None) -> dict[str, str]:
    with closing(_connect(path)) as db:
        rows = db.execute(
            "SELECT label, content FROM evaluation_outputs WHERE case_id = ? ORDER BY label",
            (case_id,),
        )
        return {row["label"]: row["content"] for row in rows}


def _require_ready(db: sqlite3.Connection, case_id: int) -> None:
    row = db.execute("SELECT packet_ready_at FROM evaluation_cases WHERE id = ?", (case_id,)).fetchone()
    if row is None or row["packet_ready_at"] is None:
        raise ValueError("The study needs three frozen outputs before recording feedback.")


def record_review(
    case_id: int, reviewer: str, ratings: dict[str, dict[str, int]], notes: dict[str, str],
    path: Path | None = None,
) -> int:
    reviewer = _text(reviewer, "Reviewer alias", 80)
    if ratings.keys() != set(LABELS) or any(scores.keys() != RUBRIC.keys() for scores in ratings.values()):
        raise ValueError("Score every rubric item for all three outputs.")
    if any(type(score) is not int or score not in SCORE_LABELS for scores in ratings.values() for score in scores.values()):
        raise ValueError("Choose 0, 1, or 2 for every rubric item.")
    clean_notes = {label: _text(notes.get(label), "Review note", 2_000, required=False) for label in LABELS}
    for label, scores in ratings.items():
        if (scores["new_risk"] == 2 or scores["grounding"] == 2) and not clean_notes[label]:
            raise ValueError(f"Add a note for output {label} naming the overlooked risk or grounded claim behind the top score.")
    with closing(_connect(path)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        _require_ready(db, case_id)
        state = _feedback_status(db, case_id)
        if state["review_count"] >= state["required_reviews"]:
            raise ValueError("This case already has its registered number of independent reviews.")
        review = db.execute(
            """INSERT INTO evaluation_reviews (case_id, reviewer, reviewer_key, rubric_version, created_at)
               VALUES (?, ?, ?, ?, ?) ON CONFLICT (case_id, reviewer_key) DO NOTHING""",
            (case_id, reviewer, reviewer.casefold(), RUBRIC_VERSION, _now()),
        )
        if not review.rowcount:
            raise ValueError("This reviewer has already submitted scores for this case.")
        review_id = int(review.lastrowid)
        db.executemany(
            "INSERT INTO evaluation_scores (review_id, label, criterion, score) VALUES (?, ?, ?, ?)",
            ((review_id, label, criterion, score) for label, scores in ratings.items() for criterion, score in scores.items()),
        )
        db.executemany(
            "INSERT INTO evaluation_review_notes (review_id, label, note) VALUES (?, ?, ?)",
            ((review_id, label, note) for label, note in clean_notes.items()),
        )
        return review_id


def record_founder_feedback(
    case_id: int, preference: str, novelty: dict[str, dict[str, str]], path: Path | None = None,
) -> None:
    if preference not in (*LABELS, "tie") or novelty.keys() != set(LABELS):
        raise ValueError("Choose a preference and provide a novelty response for each output.")
    clean = {
        label: {dimension: _text(values.get(dimension), "Founder novelty", 1_000, required=False)
                for dimension in ("competitor", "risk")}
        for label, values in novelty.items()
    }
    with closing(_connect(path)) as db, db:
        _require_ready(db, case_id)
        recorded = db.execute(
            """INSERT INTO evaluation_founder_feedback (case_id, created_at, preference)
               VALUES (?, ?, ?) ON CONFLICT (case_id) DO NOTHING""",
            (case_id, _now(), preference),
        )
        if not recorded.rowcount:
            raise ValueError("This founder feedback is already recorded.")
        db.executemany(
            "INSERT INTO evaluation_founder_novelty (case_id, label, competitor, risk) VALUES (?, ?, ?, ?)",
            ((case_id, label, values["competitor"], values["risk"]) for label, values in clean.items()),
        )


def submitted_reviews(case_id: int, path: Path | None = None) -> list[dict]:
    with closing(_connect(path)) as db:
        return [dict(row) for row in db.execute(
            "SELECT id, reviewer, created_at FROM evaluation_reviews WHERE case_id = ? ORDER BY id", (case_id,)
        )]


def _feedback_status(db: sqlite3.Connection, case_id: int) -> dict | None:
    row = db.execute(
        """SELECT required_reviews,
                  (SELECT COUNT(*) FROM evaluation_reviews WHERE case_id = evaluation_cases.id) AS review_count,
                  EXISTS (SELECT 1 FROM evaluation_founder_feedback WHERE case_id = evaluation_cases.id) AS founder_recorded
           FROM evaluation_cases WHERE id = ?""",
        (case_id,),
    ).fetchone()
    if row is None:
        return None
    return {**dict(row), "can_reveal": row["review_count"] >= row["required_reviews"] and bool(row["founder_recorded"])}


def feedback_status(case_id: int, path: Path | None = None) -> dict | None:
    with closing(_connect(path)) as db:
        return _feedback_status(db, case_id)


def reveal_review(case_id: int, review_id: int, path: Path | None = None) -> dict | None:
    """Return an exportable mapping only for a complete review of this case."""
    with closing(_connect(path)) as db, db:
        db.execute("BEGIN")
        state = _feedback_status(db, case_id)
        if state is None or not state["can_reveal"]:
            return None
        case = db.execute("SELECT * FROM evaluation_cases WHERE id = ?", (case_id,)).fetchone()
        review = db.execute(
            """SELECT id, reviewer, created_at, rubric_version FROM evaluation_reviews
               WHERE id = ? AND case_id = ?""",
            (review_id, case_id),
        ).fetchone()
        if case is None or review is None:
            return None
        scores = {label: {} for label in LABELS}
        for row in db.execute("SELECT label, criterion, score FROM evaluation_scores WHERE review_id = ?", (review_id,)):
            scores[row["label"]][row["criterion"]] = row["score"]
        if review["rubric_version"] != RUBRIC_VERSION or any(items.keys() != RUBRIC.keys() for items in scores.values()):
            return None
        notes = {row["label"]: row["note"] for row in db.execute(
            "SELECT label, note FROM evaluation_review_notes WHERE review_id = ?", (review_id,)
        )}
        outputs = []
        for row in db.execute(
            "SELECT label, condition, content FROM evaluation_outputs WHERE case_id = ? ORDER BY label", (case_id,)
        ):
            label = row["label"]
            outputs.append({**dict(row), "scores": scores[label], "reviewer_note": notes.get(label, ""),
                            "experiment_design_score": sum(scores[label][criterion] for criterion in EXPERIMENT_CRITERIA)})
        if len(outputs) != len(LABELS):
            return None
        founder = db.execute(
            "SELECT created_at, preference FROM evaluation_founder_feedback WHERE case_id = ?", (case_id,)
        ).fetchone()
        if founder:
            founder = {**dict(founder), "novelty": [dict(row) for row in db.execute(
                "SELECT label, competitor, risk FROM evaluation_founder_novelty WHERE case_id = ? ORDER BY label", (case_id,)
            )]}
        return {
            "case": dict(case), "review": dict(review), "outputs": outputs, "founder_feedback": founder,
            "rubric": {key: {"name": name, "criterion": criterion} for key, (name, criterion) in RUBRIC.items()},
            "scoring_scale": SCORE_LABELS, "experiment_criteria": EXPERIMENT_CRITERIA, "limitations": LIMITATIONS,
        }
