"""SQLite storage for completed and partial reports in the local workspace."""

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def database_path() -> Path:
    default = Path(__file__).resolve().parents[1] / ".local" / "runs.sqlite3"
    return Path(os.environ.get("IDEA_DILIGENCE_DB", default)).expanduser()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute(
        """CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, title TEXT NOT NULL,
            mode TEXT NOT NULL, report TEXT NOT NULL
        )"""
    )
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
