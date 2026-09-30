"""The only place that talks to Claude: structured-output calls, batches, cost accounting.
Every call is reported to `on_usage` so spend is logged per purpose."""

from __future__ import annotations

import json
from typing import Callable

import anthropic

# $ per million tokens: (input, output, cache read). Cache writes bill at 1.25x input.
# Min cacheable prompt: 512 tokens on Opus/Sonnet 5.5, 4096 on Haiku 4.5.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-haiku-4-5": (1.0, 5.0, 0.10),
}
DEFAULT_MODEL = "claude-opus-5-5"
MODELS = list(PRICES)
# Models that support server-side refusal fallbacks.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-opus-5", "claude-fable-5-1"}

UsageSink = Callable[[str, bool, object, float, str], None]  # model, batch, usage, cost, purpose

_sdk_client: anthropic.Anthropic | None = None


class LLMError(Exception):
    pass


def prices(model: str) -> tuple[float, float, float]:
    return PRICES.get(model, PRICES[DEFAULT_MODEL])


def cost(model: str, usage, batch: bool = False) -> float:
    price_in, price_out, price_cache = prices(model)
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    usd = (usage.input_tokens * price_in + cache_read * price_cache + cache_write * price_in * 1.25
           + usage.output_tokens * price_out) / 1e6
    return usd * (0.5 if batch else 1)


def model_of(profile: dict) -> str:
    return (profile.get("claude") or {}).get("model", DEFAULT_MODEL)


class LlmClient:
    def __init__(self, on_usage: UsageSink | None = None):
        self.on_usage = on_usage

    @staticmethod
    def sdk() -> anthropic.Anthropic:
        global _sdk_client
        if _sdk_client is None:
            _sdk_client = anthropic.Anthropic()
        return _sdk_client

    @staticmethod
    def reset():
        """Call after the API key changes (e.g. saved from the Settings page)."""
        global _sdk_client
        _sdk_client = None

    @staticmethod
    def params(profile: dict, system, content, schema: dict, max_tokens: int = 4000,
               effort: str | None = None) -> dict:
        config = profile.get("claude") or {}
        model = model_of(profile)
        output_config = {"format": {"type": "json_schema", "schema": schema}}
        if not model.startswith("claude-haiku"):  # Haiku 4.5 rejects the effort parameter
            output_config["effort"] = effort or config.get("effort", "low")
        return dict(model=model, max_tokens=max_tokens, system=system, output_config=output_config,
                    messages=[{"role": "user", "content": content}])

    def create(self, params: dict):
        if params["model"] in FALLBACK_MODELS:
            return self.sdk().beta.messages.create(**params, betas=["server-side-fallback-2026-07-01"],
                                                   fallbacks="default")
        return self.sdk().messages.create(**params)

    @staticmethod
    def parse(message) -> dict:
        if message.stop_reason == "refusal":
            raise LLMError("Claude declined this request")
        if message.stop_reason == "max_tokens":
            raise LLMError("response was cut off (max_tokens)")
        text = next((block.text for block in message.content if block.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError(f"invalid JSON from model: {e}") from e

    def record(self, message, purpose: str, batch: bool = False) -> float:
        usd = cost(message.model, message.usage, batch)
        if self.on_usage:
            self.on_usage(message.model, batch, message.usage, usd, purpose)
        return usd

    def ask(self, purpose: str, profile: dict, system, content, schema: dict, **kw) -> dict:
        """One structured call, logged under `purpose`. Raises LLMError / anthropic errors."""
        message = self.create(self.params(profile, system, content, schema, **kw))
        self.record(message, purpose)
        return self.parse(message)

    def count_tokens(self, model: str, system, content) -> int:
        return self.sdk().messages.count_tokens(
            model=model, system=system, messages=[{"role": "user", "content": content}]).input_tokens

    # --- Message Batches (50% cheaper, async) ---

    def submit_batch(self, requests: dict[str, dict]) -> str:
        """requests: custom_id -> params. Returns the batch id."""
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        batch = self.sdk().messages.batches.create(requests=[
            Request(custom_id=custom_id, params=MessageCreateParamsNonStreaming(**params))
            for custom_id, params in requests.items()])
        return batch.id

    def batch_ended(self, batch_id: str) -> bool:
        return self.sdk().messages.batches.retrieve(batch_id).processing_status == "ended"

    def batch_results(self, batch_id: str):
        return self.sdk().messages.batches.results(batch_id)
