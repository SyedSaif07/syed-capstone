"""W4 — scripts/compare_models.py

Lab Step 3 — run the same questions through two OpenAI models and persist
both result sets to SQLite (the W4 store has a `model` column for this).

Usage:
    # Defaults: gpt-4o-mini vs gpt-4o, 10 questions from data/questions.csv
    python scripts/compare_models.py

    # Override:
    python scripts/compare_models.py \\
        --models gpt-4o-mini,gpt-4o \\
        --questions data/questions.csv \\
        --db data/answers.db

After the run, inspect the persisted rows with:
    sqlite3 data/answers.db "SELECT model, COUNT(*), ROUND(SUM(cost_usd), 6) FROM answers GROUP BY model;"
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
import time
from pathlib import Path

# Make the `src` package reachable when invoked as `python scripts/X.py`.
# Without this, Python's sys.path[0] is `scripts/` (the script's directory),
# not the project root, so `from src.pipeline...` raises ModuleNotFoundError.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.models import Question
from src.pipeline.pipeline import ask_llm
from src.pipeline.settings import Settings
from src.pipeline.store import connect, save_answer


async def run_one_model(questions: list[str], model: str, db_path: Path) -> dict:
    """Run all questions through one model. Returns aggregate stats."""
    settings = Settings(model=model)
    start = time.perf_counter()
    total_cost = 0.0
    total_retries = 0

    with connect(db_path) as conn:
        for q in questions:
            answer = await ask_llm(Question(question=q), settings)
            total_cost += answer.cost_usd
            total_retries += answer.retries
            save_answer(
                conn,
                question=q,
                content=answer.content,
                retries=answer.retries,
                cost_usd=answer.cost_usd,
                model=model,
                confidence=answer.confidence,
                sources=answer.sources,
                schema_version=answer.schema_version,
            )

    elapsed = time.perf_counter() - start
    return {
        "model": model,
        "n": len(questions),
        "total_cost_usd": round(total_cost, 6),
        "total_retries": total_retries,
        "elapsed_s": round(elapsed, 2),
        "avg_cost_usd": round(total_cost / len(questions), 6),
    }


def load_questions(path: Path) -> list[str]:
    """Read questions from a one-column CSV (header optional)."""
    with path.open() as f:
        reader = csv.reader(f)
        rows = list(reader)
    if rows and rows[0] and rows[0][0].lower().startswith("question"):
        rows = rows[1:]  # skip header
    return [row[0] for row in rows if row and row[0].strip()]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run two-model comparison for W4 Lab Step 3")
    p.add_argument("--models", default="gpt-4o-mini,gpt-4o",
                   help="Comma-separated model ids (default: gpt-4o-mini,gpt-4o)")
    p.add_argument("--questions", default="data/questions.csv",
                   help="Path to questions CSV (default: data/questions.csv)")
    p.add_argument("--db", default="data/answers.db",
                   help="Path to SQLite db (default: data/answers.db)")
    return p.parse_args(argv)


async def main_async(args: argparse.Namespace) -> int:
    questions = load_questions(Path(args.questions))
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"Running {len(questions)} questions through: {', '.join(models)}")
    print(f"Persisting to: {db_path}")
    print()

    summaries = []
    for m in models:
        print(f"  → {m} …")
        summary = await run_one_model(questions, m, db_path)
        summaries.append(summary)
        print(
            f"    done — n={summary['n']}  "
            f"cost=${summary['total_cost_usd']}  "
            f"avg=${summary['avg_cost_usd']}/q  "
            f"retries={summary['total_retries']}  "
            f"time={summary['elapsed_s']}s"
        )

    print()
    print("=" * 60)
    print(f"{'Model':<20}  {'n':>4}  {'Total $':>10}  {'Avg $/q':>10}  {'Time':>8}")
    print("-" * 60)
    for s in summaries:
        print(
            f"{s['model']:<20}  {s['n']:>4}  "
            f"{s['total_cost_usd']:>10.6f}  "
            f"{s['avg_cost_usd']:>10.6f}  "
            f"{s['elapsed_s']:>7.2f}s"
        )
    if len(summaries) == 2:
        a, b = summaries
        ratio = b["total_cost_usd"] / a["total_cost_usd"] if a["total_cost_usd"] else 0
        print()
        print(f"  → {b['model']} cost {ratio:.1f}× more than {a['model']} on the same questions.")
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
