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
import time

from .fake_llm import Question, Answer, fake_ask_llm, FakeLLMError


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 (sub-step 2e) — structured (JSON) logging
#
# TODO 2e: Replace this commented block with:
#   - A `JsonFormatter(logging.Formatter)` class whose `format(record)` returns
#     `json.dumps({"ts": ..., "level": ..., "msg": ...})`
#   - A module-level `log = logging.getLogger("pipeline")` + setLevel(INFO)
#   - A StreamHandler attached to that logger, using JsonFormatter()
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# 2b — single LLM call
# ─────────────────────────────────────────────────────────────────────────────
async def ask_llm(q: Question, fail_rate: float = 0.0) -> Answer:
    """One LLM call. Fake for now; real client wired in via Settings.use_fake later."""
    return await fake_ask_llm(q, fail_rate=fail_rate)
    # raise NotImplementedError("Step 2 — call fake_ask_llm and return the Answer")


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


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint — replaced in Step 3a (Settings) and again in Step 3c (CSV + batched)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    fail_rate = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0

    sample = [
        Question(text="What is RAG in one sentence?"),
        Question(text="Name three uses of vector databases."),
        Question(text="Why might an LLM hallucinate?"),
    ]
    answers = asyncio.run(run_batch(sample, fail_rate=fail_rate))
    for a in answers:
        print(f"- {a.text[:80]}")
