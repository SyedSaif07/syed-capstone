"""W4 REFERENCE — src/pipeline/store.py

Extends the W2 SQLite store with two new columns:
  • cost_usd  REAL    — actual per-call cost from response.usage × rates
  • model     TEXT    — which model produced the answer

Adds ensure_schema() that runs idempotent ALTER TABLE migrations so a cohort
member can rerun without breaking an existing answers.db.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


# ─── Schema (idempotent) ────────────────────────────────────────────────────
_BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question        TEXT NOT NULL,
    content         TEXT NOT NULL,
    retries         INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

# Columns added in W4. Each entry: (column_name, column_def).
# Applied via ALTER TABLE only if missing — so the migration is safe to rerun.
_W4_NEW_COLUMNS = [
    ("model",          "TEXT"),
    ("confidence",     "REAL"),
    ("sources_json",   "TEXT"),  # list[str] stored as JSON
    ("schema_version", "TEXT DEFAULT 'v1'"),
]


def ensure_schema(db_path: str | Path) -> None:
    """Create answers table if missing, then add any missing W4 columns.

    Safe to call on an empty file, on a W2/W3 db, or on a fully-migrated db.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(_BASE_SCHEMA)
        # Read current columns.
        cur = conn.execute("PRAGMA table_info(answers)")
        existing = {row[1] for row in cur.fetchall()}
        for col_name, col_def in _W4_NEW_COLUMNS:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE answers ADD COLUMN {col_name} {col_def}")
        conn.commit()
    finally:
        conn.close()


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open a connection with the W4 schema guaranteed in place."""
    ensure_schema(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_answer(
    conn: sqlite3.Connection,
    *,
    question: str,
    content: str,
    retries: int,
    cost_usd: float,
    model: str,
    confidence: float,
    sources: list[str],
    schema_version: str = "v1",
) -> int:
    """Insert one row and return its rowid."""
    cur = conn.execute(
        """
        INSERT INTO answers (
            question, content, retries, cost_usd, model,
            confidence, sources_json, schema_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            question, content, retries, cost_usd, model,
            confidence, json.dumps(sources), schema_version,
        ),
    )
    return cur.lastrowid


def query_results(conn: sqlite3.Connection, model: str | None = None) -> list[dict]:
    """Read back rows, optionally filtered by model. Useful in Step 3."""
    if model is None:
        cur = conn.execute("SELECT * FROM answers ORDER BY id")
    else:
        cur = conn.execute("SELECT * FROM answers WHERE model = ? ORDER BY id", (model,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]