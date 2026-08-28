"""Async batch pipeline — STARTER file for Week 2.

You will complete this file across sub-steps 2b → 2e. Each stub maps to one
sub-step:
  - ask_llm                — 2b
  - ask_llm_with_retry      — 2c
  - run_batch               — 2d
  - JSON-logging block      — 2e

After Step 2a, you renamed this file to `src/pipeline/pipeline.py` and changed
the `from fake_llm import ...` import below to `from .fake_llm import ...`.

The completed reference is at <cohort-repo>/week2/reference/pipeline_reference.py.
"""
from __future__ import annotations
import asyncio
import json
import logging
import sys
import os
from pathlib import Path
import time
from .logging_config import get_logger
from .settings import Settings, RunSummary
import csv



_settings_for_import = Settings()

if _settings_for_import.use_fake:
    from .fake_llm import Question, Answer, fake_ask_llm, FakeLLMError
else:
    from dotenv import load_dotenv
    from openai import AsyncOpenAI
    from pydantic import BaseModel



    BASE_DIR = Path(__file__).resolve().parent.parent
    load_dotenv(BASE_DIR / ".env")

    _client = AsyncOpenAI(base_url="https://openai.vocareum.com/v1")

    class Question(BaseModel):
        text: str

    class Answer(BaseModel):
        question: str
        text:     str
        cost_usd: float
        retries:  int = 0

# ─────────────────────────────────────────────────────────────────────────────
# Step 5 (sub-step 2e) — structured (JSON) logging
#
# TODO 2e: Replace this commented block with:
#   - A `JsonFormatter(logging.Formatter)` class whose `format(record)` returns
#     `json.dumps({"ts": ..., "level": ..., "msg": ...})`
#   - A module-level `log = logging.getLogger("pipeline")` + setLevel(INFO)
#   - A StreamHandler attached to that logger, using JsonFormatter()
# ─────────────────────────────────────────────────────────────────────────────
log = get_logger()

def load_questions(path: str | Path = "data/questions_small.csv") -> list[Question]:
    """Read questions from a CSV with a `text` column."""
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return [Question(text=row["text"]) for row in rows if row.get("text")]



# ─────────────────────────────────────────────────────────────────────────────
# 2b — single LLM call
# ─────────────────────────────────────────────────────────────────────────────
async def ask_llm(q: Question, fail_rate: float = 0.0) -> Answer:
    """One LLM call. Branches on Settings.use_fake."""
    if _settings_for_import.use_fake:
        ans = await fake_ask_llm(q, fail_rate=fail_rate)
    else:
        resp = await _client.chat.completions.create(
            model=_settings_for_import.model,
            messages=[{"role": "user", "content": q.text}],
        )
        ans = Answer(
            question=q.text,
            text=resp.choices[0].message.content,
            cost_usd=0.0001,                  # real cost-from-usage lands in W25
        )
    log.info(f"asked: {q.text[:40]}")
    return ans


# ─────────────────────────────────────────────────────────────────────────────
# 2c — retry wrapper
# ─────────────────────────────────────────────────────────────────────────────
async def ask_llm_with_retry(
    q: Question, tries: int = 3, fail_rate: float = 0.0
) -> Answer:
    """Retry up to `tries` times. Wait 1 s, 2 s, 4 s between attempts."""
    for attempt in range(tries):
        try:
            ans = await ask_llm(q, fail_rate=fail_rate)
            ans.retries = attempt
            return ans
        except Exception as exc:
            if attempt == tries - 1:
                raise
            log.warning(f"retry {attempt + 1} for: {q.text[:40]} ({exc})")
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError("unreachable")          # pragma: no cover
    # raise NotImplementedError("Step 3 — wrap ask_llm with retry + exponential backoff")


# ─────────────────────────────────────────────────────────────────────────────
# 2d — batch runner
# ─────────────────────────────────────────────────────────────────────────────
async def run_batch(
    questions: list[Question], fail_rate: float = 0.0
) -> list[Answer]:
    """Fire every question in parallel via asyncio.gather (with retries)."""
    tasks = [ask_llm_with_retry(q, fail_rate=fail_rate) for q in questions]
    return await asyncio.gather(*tasks)
    # raise NotImplementedError("Step 4 — build the tasks list and gather them")



async def run_in_batches(
    questions: list[Question],
    batch_size: int = 5,
    fail_rate: float = 0.0,
) -> list[Answer]:
    """Fire questions in chunks of `batch_size`, with a 100 ms pause between batches."""
    out: list[Answer] = []
    for i in range(0, len(questions), batch_size):
        chunk = questions[i : i + batch_size]
        log.info(f"batch {i // batch_size + 1}: {len(chunk)} questions")
        batch_answers = await asyncio.gather(
            *(ask_llm_with_retry(q, fail_rate=fail_rate) for q in chunk)
        )
        out.extend(batch_answers)
        await asyncio.sleep(0.1)              # gentle pace between batches
    return out


def summarise_run(
    answers: list[Answer],
    *,
    started_at: float,
    elapsed: float,
    fail_rate: float,
    use_fake: bool,
) -> RunSummary:
    """Roll a list of Answers + wall-clock data into a RunSummary."""
    return RunSummary(
        started_at      = started_at,
        elapsed_seconds = elapsed,
        n_questions     = len(answers),
        n_succeeded     = len(answers),
        n_retries_total = sum(a.retries  for a in answers),
        total_cost_usd  = sum(a.cost_usd for a in answers),
        fail_rate       = fail_rate,
        use_fake        = use_fake,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint — replaced in Step 3a (Settings) and again in Step 3c (CSV + batched)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    settings = Settings()
    log.info(f"config: {settings.model_dump(mode='json')}")
    # fail_rate = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0

    # sample = [
    #     Question(text="What is RAG in one sentence?"),
    #     Question(text="Name three uses of vector databases."),
    #     Question(text="Why might an LLM hallucinate?"),
    # ]

    questions = load_questions(settings.questions_csv)
    log.info(f"loaded {len(questions)} questions")

    started = time.time()
    answers = asyncio.run(
        run_in_batches(
            questions,
            batch_size=settings.batch_size,
            fail_rate=settings.fail_rate,
        )
    )
    elapsed = time.time() - started

    summary = summarise_run(
        answers,
        started_at = started,
        elapsed    = elapsed,
        fail_rate  = settings.fail_rate,
        use_fake   = settings.use_fake,
    )
    log.info(f"summary: {summary.model_dump_json()}")

    # Write the structured artefact
    settings.results_json.write_text(
        json.dumps({
            "summary": summary.model_dump(mode="json"),
            "answers": [a.model_dump() for a in answers],
        }, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(answers)} answers to {settings.results_json} in {elapsed:.2f}s")

    # SQLite persistence
    # Deferred import: store.py imports Answer from this module; top-level import
    # would cause a circular import.
    from .store import connect, write_run, write_answers
    with connect(settings.results_db) as con:
        run_id = write_run(con, summary)
        n = write_answers(con, run_id, answers)
    log.info(f"persisted run {run_id} with {n} answers to {settings.results_db}")

    # answers = asyncio.run(run_batch(sample, fail_rate=settings.fail_rate))
    # for a in answers:
    #     print(f"- {a.text[:80]}")

    # ans = asyncio.run(ask_llm(Question(text="What is RAG in onesentence?")))
    # print('type:', type(ans).__name__)
    # print('text:', ans.text[:80])
    # print('cost:', ans.cost_usd)
    # print('retries:', ans.retries)

    # ans = asyncio.run(ask_llm_with_retry(Question(text='What is RAG?')))
    # print('clean: retries =', ans.retries)
    # # Always-fail — should retry twice (3 attempts total) and then raise
    # try:
    #     asyncio.run(ask_llm_with_retry(Question(text='What is RAG?'), fail_rate=0.5))
    # except Exception as e:
    #     print('lossy: raised after 3 attempts:', type(e).__name__)

    # questions = [
    #     Question(text='What is RAG?'),
    #     Question(text='Name three uses of vector databases.'),
    #     Question(text='Why might an LLM hallucinate?'),
    #     ]
    # t0 = time.time()
    # answers = asyncio.run(run_batch(questions))
    # elapsed = time.time() - t0
    # print(f'wall-clock: {elapsed:.2f}s')
    # for a in answers:
    #     print(f'- {a.text[:60]}')

