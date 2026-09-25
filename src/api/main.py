"""api/main.py — STARTER for Week 3 Lab Step 1.

You will complete this file across sub-steps 1b → 1f. Each TODO matches a
sub-step in the lab guide.

The completed reference is at <cohort-repo>/week3/reference/api_main_reference.py.

Architecture note: this file holds the *public* W3 API contract — Question
with field `question`, Answer with fields `content/cost_usd/retries`. These
are locked in ADR 0002. Internally we delegate to the W2 pipeline's
`ask_llm`, whose Question has field `text` and whose Answer has field `text`.
The translation happens inside each endpoint.
"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.pipeline.logging_config import get_logger
from src.pipeline.pipeline import Answer as _PipelineAnswer
from src.pipeline.pipeline import Question as _PipelineQuestion
# W2 pipeline — the underlying engine
from src.pipeline.pipeline import ask_llm as _pipeline_ask_llm
from src.pipeline.pipeline import stream_answer
from src.pipeline.settings import Settings

log = get_logger()
_settings = Settings()


# ─────────────────────────────────────────────────────────────────────────────
# Public W3 API models — locked in ADR 0002
# ─────────────────────────────────────────────────────────────────────────────
class Question(BaseModel):
    """Public request shape. Field name `question`, not `text`."""
    question: str


class Answer(BaseModel):
    """Public response shape. Field name `content`, not `text`."""
    content: str
    cost_usd: float
    retries: int


# ─────────────────────────────────────────────────────────────────────────────
# 1b — Replace the placeholder below with a real FastAPI app instance.
# ─────────────────────────────────────────────────────────────────────────────
# app = None  # TODO 1b — replace with FastAPI(title="...", description="...", version="...")

app = FastAPI(
    title="Capstone API",
    description="Wraps the W2 async pipeline. Contract locked in ADR 0002 (W3); internals upgraded W4+.",
    version="1.0.0",
)


# ─────────────────────────────────────────────────────────────────────────────
# 1c — Add the /ask_batched endpoint (non-streaming reference).
#
# Translate W3 Question → W2 _PipelineQuestion(text=q.question), then call
# _pipeline_ask_llm, then translate the W2 Answer → W3 Answer.
#
# Shape:
#   @app.post("/ask_batched", response_model=Answer)
#   async def ask_batched(q: Question) -> Answer:
#       pipeline_q = _PipelineQuestion(text=q.question)
#       pipeline_ans = await _pipeline_ask_llm(pipeline_q)
#       return Answer(
#           content=pipeline_ans.text,
#           cost_usd=pipeline_ans.cost_usd,
#           retries=pipeline_ans.retries,
#       )
# ─────────────────────────────────────────────────────────────────────────────

# TODO 1c — add /ask_batched here
@app.post("/ask_batched", response_model=_PipelineAnswer)
async def ask_batched(q: Question) -> _PipelineAnswer:
    """Non-streaming. Returns the full Answer in a single JSON body."""
    log.info("ask_batched  question=%r", q.question[:80])
    pipeline_q = _PipelineQuestion(question=q.question)
    pipeline_ans = await _pipeline_ask_llm(pipeline_q)
    # return Answer(
    #     content=pipeline_ans.content,
    #     cost_usd=pipeline_ans.cost_usd,
    #     retries=pipeline_ans.retries,
    # )
    return pipeline_ans


# ─────────────────────────────────────────────────────────────────────────────
# 1d — Add /health.
# ─────────────────────────────────────────────────────────────────────────────

# TODO 1d — add @app.get("/health") returning {"status": "ok"}
@app.get("/health")
async def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# 1f — Add stream_answer + the streaming /ask endpoint.
#
# stream_answer(question_text: str) is an async generator that:
#   - builds _PipelineQuestion(text=question_text)
#   - awaits _pipeline_ask_llm to get a full pipeline Answer
#   - yields words from pipeline_ans.text.split(" ") with " " appended
#   - awaits asyncio.sleep(0.05) between yields
#
# The /ask endpoint returns StreamingResponse(stream_answer(q.question), media_type="text/plain").
# ─────────────────────────────────────────────────────────────────────────────

# TODO 1f — add stream_answer + /ask here
# async def stream_answer(question_text: str):
#     """Async generator yielding the answer word-by-word.
#
#     W3 streams from FastAPI to the client; the pipeline call itself is still
#     non-streaming. In W4 the LLM call becomes a real stream end-to-end — this
#     generator's shape doesn't change, only what fills it.
#     """
#     pipeline_q = _PipelineQuestion(question=question_text)
#     pipeline_ans = await _pipeline_ask_llm(pipeline_q)
#     for word in pipeline_ans.text.split(" "):
#         yield word + " "
#         await asyncio.sleep(0.05)


@app.post("/ask")
async def ask(q: Question):
    """Streaming /ask — the contracted endpoint."""

    # log.info("ask  question=%r", q.question[:80])
    # return StreamingResponse(
    #     stream_answer(q.question),
    #     media_type="text/plain",
    # )
    async def _gen():
        async for chunk in stream_answer(q.question, _settings):
            yield chunk

    return StreamingResponse(_gen(), media_type="text/plain")
