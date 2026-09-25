"""W4 — tests/test_cost.py

Pure unit tests. No API key required, no network. Should pass in under 50 ms.
"""
import pytest

from src.pipeline.cost import RATES, compute_cost_usd


class TestComputeCostUsd:

    def test_gpt_4o_mini_at_known_token_counts(self):
        """gpt-4o-mini: $0.15/M in, $0.60/M out.
        100 prompt + 50 completion → (100*0.15 + 50*0.60) / 1M = 45 / 1M.
        """
        cost = compute_cost_usd("gpt-4o-mini", 100, 50)
        assert cost == pytest.approx(45.0 / 1_000_000, rel=1e-9)

    def test_gpt_4o_at_known_token_counts(self):
        """gpt-4o: $2.50/M in, $10.00/M out.
        100 prompt + 50 completion → (100*2.50 + 50*10.00) / 1M = 750 / 1M.
        """
        cost = compute_cost_usd("gpt-4o", 100, 50)
        assert cost == pytest.approx(750.0 / 1_000_000, rel=1e-9)

    def test_zero_tokens_costs_nothing(self):
        assert compute_cost_usd("gpt-4o-mini", 0, 0) == 0.0

    def test_unknown_model_returns_zero_not_raises(self):
        """Defensive: an unknown model in a batch run should not blow up
        the whole batch. It returns 0.0 so the call is logged as 'free'."""
        cost = compute_cost_usd("never-shipped-by-anyone", 1000, 1000)
        assert cost == 0.0

    def test_gpt_4o_is_more_expensive_than_gpt_4o_mini(self):
        """Sanity check the relative cost story we tell in the deck."""
        same_tokens = (500, 200)
        mini = compute_cost_usd("gpt-4o-mini", *same_tokens)
        full = compute_cost_usd("gpt-4o", *same_tokens)
        assert full > mini
        # Order-of-magnitude check — should be roughly 15× more expensive
        # for input. (The ratio is closer to 13–16× depending on the mix.)
        assert full / mini > 5

    def test_ollama_model_is_free(self):
        """Local Ollama models are pre-registered with $0 rates."""
        assert compute_cost_usd("llama3.2:3b", 10_000, 5_000) == 0.0


class TestRatesTable:

    def test_required_lab_models_present(self):
        """The two OpenAI models used in the lab MUST be in RATES."""
        assert "gpt-4o-mini" in RATES
        assert "gpt-4o" in RATES

    def test_rates_are_input_output_tuples(self):
        """Each entry is (input_rate, output_rate); both non-negative floats."""
        for model, rates in RATES.items():
            assert isinstance(rates, tuple), f"{model}: rates must be a tuple"
            assert len(rates) == 2, f"{model}: rates must be (in, out)"
            in_rate, out_rate = rates
            assert in_rate >= 0, f"{model}: input rate must be >= 0"
            assert out_rate >= 0, f"{model}: output rate must be >= 0"

    def test_output_rate_at_least_input_for_paid_models(self):
        """Across providers, completion tokens cost more than prompt tokens.
        This is a sanity check; it must hold for any paid model added later."""
        for model, (in_rate, out_rate) in RATES.items():
            if in_rate == 0.0 and out_rate == 0.0:
                continue  # skip Ollama / free local models
            assert out_rate >= in_rate, (
                f"{model}: output rate ({out_rate}) "
                f"should be >= input rate ({in_rate})"
            )
