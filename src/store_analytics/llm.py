"""Unified LLM wrapper — Groq (agent) and Mistral (judge)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import groq
from mistralai.client import Mistral

from . import config


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""

    content: str | None
    tool_calls: list[dict[str, Any]]
    prompt_tokens: int
    completion_tokens: int
    model: str
    provider: str
    latency_ms: float


class LLMClient:
    """Thin wrapper that routes calls to Groq or Mistral."""

    def __init__(self) -> None:
        self._groq: groq.Groq | None = None
        self._mistral: Mistral | None = None

    def _get_groq(self) -> groq.Groq:
        if self._groq is None:
            if not config.GROQ_API_KEY:
                raise ValueError("GROQ_API_KEY not set")
            self._groq = groq.Groq(api_key=config.GROQ_API_KEY)
        return self._groq

    def _get_mistral(self) -> Mistral:
        if self._mistral is None:
            if not config.MISTRAL_API_KEY:
                raise ValueError("MISTRAL_API_KEY not set")
            self._mistral = Mistral(api_key=config.MISTRAL_API_KEY)
        return self._mistral

    @staticmethod
    def _call_with_retry(fn, *, max_attempts: int = 4, base_delay: float = 2.0) -> Any:
        """Retry with exponential backoff on rate-limit errors (HTTP 429).

        The eval harness fires many agent/judge calls back-to-back against free-tier
        rate limits (Groq TPM, Mistral RPM), which throttle fast. Without this, a
        429 either crashes run_agent() mid-loop (leaking the raw error as the
        "final answer") or silently degrades trajectory_quality to a fake default.
        """
        for attempt in range(max_attempts):
            try:
                return fn()
            except Exception as e:
                is_last = attempt == max_attempts - 1
                if is_last or "429" not in str(e):
                    raise
                time.sleep(base_delay * (2 ** attempt))

    def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        provider: str = "groq",
        model: str | None = None,
        max_tokens: int = config.MAX_TOKENS_AGENT,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Call an LLM and return a normalized response."""
        if provider == "groq":
            return self._call_groq(messages, tools, model or config.AGENT_MODEL, max_tokens, temperature)
        elif provider == "mistral":
            return self._call_mistral(messages, tools, model or config.JUDGE_MODEL, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def _call_groq(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        client = self._get_groq()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        t0 = time.perf_counter()
        response = self._call_with_retry(lambda: client.chat.completions.create(**kwargs))
        latency_ms = (time.perf_counter() - t0) * 1000

        choice = response.choices[0]
        tool_calls_raw = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                import json
                tool_calls_raw.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        usage = response.usage
        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls_raw,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
            provider="groq",
            latency_ms=latency_ms,
        )

    def _call_mistral(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        client = self._get_mistral()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools

        t0 = time.perf_counter()
        response = self._call_with_retry(lambda: client.chat.complete(**kwargs))
        latency_ms = (time.perf_counter() - t0) * 1000

        choice = response.choices[0]
        tool_calls_raw = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                import json
                tool_calls_raw.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        usage = response.usage
        return LLMResponse(
            content=choice.message.content,
            tool_calls=tool_calls_raw,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=response.model,
            provider="mistral",
            latency_ms=latency_ms,
        )


# Module-level singleton
llm_client = LLMClient()
