"""Model prices, in US dollars per MILLION tokens.

These are a snapshot and WILL drift. Two honest options in production:

  a) fetch https://openrouter.ai/api/v1/models at boot and cache the real numbers, or
  b) read OpenRouter's `usage.cost` field, which it returns already computed.

We keep a static table here because the point of Chapter 1 is to make cost *visible*, and a
table you can read beats an API call you can't. `examples/00_check_setup.py` prints live
prices so you can correct this file whenever you like.
"""

from __future__ import annotations

# model id -> (input $/M, output $/M)
PRICES: dict[str, tuple[float, float]] = {
    # Anthropic
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
    "anthropic/claude-sonnet-4.5": (3.00, 15.00),
    "anthropic/claude-opus-4.1": (15.00, 75.00),
    # OpenAI
    "openai/gpt-5-mini": (0.25, 2.00),
    "openai/gpt-5-nano": (0.05, 0.40),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    # Google
    # NOTE: gemini-2.0-flash-001 was delisted from OpenRouter; left here as a
    # reminder that model ids rot. Run examples/00_check_setup.py for live ones.
    "google/gemini-2.0-flash-001": (0.10, 0.40),
    "google/gemini-2.5-pro": (1.25, 10.00),
    # Open weights (cheap — good for eval volume)
    "meta-llama/llama-3.3-70b-instruct": (0.12, 0.30),
    "deepseek/deepseek-chat": (0.25, 1.00),
    "qwen/qwen-2.5-72b-instruct": (0.12, 0.39),
}

#: Used when a model id isn't in the table. Deliberately pessimistic — an unknown model
#: should look expensive in your logs, not free. Silent zeros hide real money.
FALLBACK: tuple[float, float] = (3.00, 15.00)


def price_per_million(model: str) -> tuple[float, float]:
    """(input, output) price per million tokens for `model`.

    Falls back to a prefix match so that `anthropic/claude-haiku-4.5:beta` or a dated
    variant still resolves sensibly.
    """
    if model in PRICES:
        return PRICES[model]
    for known, price in PRICES.items():
        if model.startswith(known) or known.startswith(model):
            return price
    return FALLBACK


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Dollar cost of one call. Note input and output are billed at different rates —
    output is typically 3-5x input, which is why verbose agents get expensive fast."""
    pin, pout = price_per_million(model)
    return (prompt_tokens / 1_000_000) * pin + (completion_tokens / 1_000_000) * pout
