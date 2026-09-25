"""W4 — scripts/migrate_store.py

One-time migration to add the W4 columns (model, confidence, sources_json,
schema_version) to an existing answers.db.

Safe to rerun. If columns already exist, nothing happens.

Usage:
    python scripts/migrate_store.py [path/to/answers.db]

The default db path is data/answers.db.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Make the `src` package reachable when invoked as `python scripts/X.py`.
# Without this, Python's sys.path[0] is `scripts/` (the script's directory),
# not the project root, so `from src.pipeline...` raises ModuleNotFoundError.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.store import ensure_schema


def main(argv: list[str]) -> int:
    db_path = Path(argv[1]) if len(argv) > 1 else Path("data/answers.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Snapshot the columns before, for the user-facing summary.
    before = _columns(db_path) if db_path.exists() else []

    ensure_schema(db_path)

    after = _columns(db_path)
    new = [c for c in after if c not in before]

    print(f"Migrated: {db_path}")
    print(f"  Columns before : {before or '(none — table created)'}")
    print(f"  Columns after  : {after}")
    if new:
        print(f"  Added          : {new}")
    else:
        print("  Added          : (none — already migrated)")
    return 0


def _columns(db_path: Path) -> list[str]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("PRAGMA table_info(answers)")
        return [row[1] for row in cur.fetchall()]
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
