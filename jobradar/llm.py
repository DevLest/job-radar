"""Shared Claude plumbing: one structured-output call, cost accounting, usage logging."""

from __future__ import annotations

import json

import anthropic

# $ per million tokens: (input, output, cache read). Cache writes bill at 1.25x input.
# Min cacheable prompt: 512 tokens on Opus/Sonnet 5.5, 4096 on Haiku 4.5.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
}
MODELS = list(PRICES)
# Models that support server-side refusal fallbacks.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5", "claude-fable-5-1"}

_client: anthropic.Anthropic | None = None


class LLMError(Exception):
    pass


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def reset_client():
    """Call after the API key changes (e.g. saved from the Settings page)."""
    global _client
    _client = None


def cost(model: str, usage, batch: bool = False) -> float:
    pin, pout, pcache = PRICES.get(model, PRICES["claude-opus-5-5"])
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    usd = (usage.input_tokens * pin + cr * pcache + cw * pin * 1.25 + usage.output_tokens * pout) / 1e6
    return usd * (0.5 if batch else 1)


def params(profile: dict, system, content, schema: dict, max_tokens: int = 4000, effort: str | None = None) -> dict:
    cfg = profile.get("claude") or {}
    model = cfg.get("model", "claude-opus-5-5")
    output_config = {"format": {"type": "json_schema", "schema": schema}}
    if not model.startswith("claude-haiku"):  # Haiku 4.5 rejects the effort parameter
        output_config["effort"] = effort or cfg.get("effort", "low")
    return dict(model=model, max_tokens=max_tokens, system=system, output_config=output_config,
                messages=[{"role": "user", "content": content}])


def create(p: dict):
    if p["model"] in FALLBACK_MODELS:
        return client().beta.messages.create(**p, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    return client().messages.create(**p)


def parse(msg) -> dict:
    if msg.stop_reason == "refusal":
        raise LLMError("Claude declined this request")
    if msg.stop_reason == "max_tokens":
        raise LLMError("response was cut off (max_tokens)")
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON from model: {e}") from e


def ask(db, purpose: str, profile: dict, system, content, schema: dict, **kw) -> dict:
    """One structured call. Logs tokens + cost under `purpose`. Raises LLMError / anthropic errors."""
    msg = create(params(profile, system, content, schema, **kw))
    db.log_usage(msg.model, False, msg.usage, cost(msg.model, msg.usage), purpose)
    return parse(msg)
