"""W4 REFERENCE — src/pipeline/cost.py

Real cost computation. response.usage tells you tokens; this module turns
tokens into USD.
"""

# Order-of-magnitude rates as of late 2025. Confirm against
# https://artificialanalysis.ai before quoting in production.
# USD per 1M tokens, (input_rate, output_rate).
RATES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o":      (2.50, 10.00),
    # Ollama models are free locally — keep them in the table so the same
    # compute_cost_usd() works for the take-home activity.
    "llama3.2:3b": (0.0, 0.0),
}


def compute_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Convert a usage tuple into USD.

    Returns 0.0 for unknown models rather than raising — a missing rate
    shouldn't break a batch run; it just means we can't price that call.
    """
    rates = RATES.get(model)
    if rates is None:
        return 0.0
    in_rate, out_rate = rates
    return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000.0
