"""tests/test_pipeline.py — REFERENCE for Week 3 Lab Step 2.

Two mocked unit tests. We mock the boundary layer (`fake_ask_llm`) and verify
behaviour of the wrappers above it.

Assumes `Settings.use_fake = True` (the W2 default) — when it's True, `ask_llm`
in the W2 pipeline calls `fake_ask_llm`, which is what we mock.

Run with:
    pytest tests/test_pipeline.py -v
"""
from unittest.mock import AsyncMock, patch
import pytest

# Import the W2 fake-LLM types (Question, Answer, FakeLLMError).
# These live in src/pipeline/fake_llm.py.
from src.pipeline.fake_llm import Question, Answer, FakeLLMError


# ─────────────────────────────────────────────────────────────────────────────
# 2b — ask_llm calls fake_ask_llm exactly once
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_ask_llm_calls_fake_once():
    """ask_llm should invoke the underlying fake_ask_llm exactly once per call.

    We mock the boundary we don't want to exercise (the fake call itself) and
    assert behaviour we do control (ask_llm calls it once, returns its result).
    """
    fake_answer = Answer(
        question="What is RAG?",
        text="Mocked answer.",
        cost_usd=0.0001,
        retries=0,
    )

    with patch(
        "src.pipeline.pipeline.fake_ask_llm",
        AsyncMock(return_value=fake_answer),
    ) as m:
        from src.pipeline.pipeline import ask_llm
        result = await ask_llm(Question(text="What is RAG?"))

    assert m.call_count == 1
    assert result.text == "Mocked answer."


# ─────────────────────────────────────────────────────────────────────────────
# 2c — ask_llm_with_retry hits 3 times on persistent failure
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_retry_three_times_on_failure():
    """ask_llm_with_retry should attempt 3 times before giving up.

    We mock fake_ask_llm to always raise FakeLLMError, and we also mock
    asyncio.sleep so the test doesn't actually wait 1 + 2 = 3 real seconds
    for the backoff.
    """
    with patch(
        "src.pipeline.pipeline.fake_ask_llm",
        AsyncMock(side_effect=FakeLLMError("simulated")),
    ) as m_call, patch(
        "src.pipeline.pipeline.asyncio.sleep",
        AsyncMock(),
    ):
        from src.pipeline.pipeline import ask_llm_with_retry
        with pytest.raises(FakeLLMError):
            await ask_llm_with_retry(Question(text="What is RAG?"), tries=3)

    assert m_call.call_count == 3
