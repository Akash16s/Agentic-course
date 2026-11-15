"""The provider shim — one place where all model traffic goes.

This file is deliberately THIN. It does four things and nothing more:

  1. builds the HTTP request (via the openai SDK, pointed at OpenRouter)
  2. normalises the response into our own `LLMResponse`
  3. translates SDK exceptions into `agentlib.errors`
  4. exposes `usage` honestly, so cost tracking is possible

It does NOT retry, cache, trace or count cost. Those are separate concerns you will add in
the exercises and in Chapters 12–13 — wrapped *around* this, not baked into it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterator

from agentlib import errors

try:  # optional at import time so the offline tests work before you pip install
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.getenv("AGENT_MODEL", "anthropic/claude-haiku-4.5")

Message = dict[str, Any]  # {"role": ..., "content": ...} and later tool fields


@dataclass(frozen=True)
class Usage:
    """Token accounting for a single call. These numbers come from the provider and are
    what you are actually billed on — never from your own estimate."""

    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.prompt_tokens + other.prompt_tokens,
            self.completion_tokens + other.completion_tokens,
        )


@dataclass
class LLMResponse:
    """One model reply, normalised."""

    text: str
    finish_reason: str = "stop"
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    #: Raw tool-call dicts from the provider, [] when the model just talked.
    #: Shape: [{"id": ..., "type": "function",
    #:          "function": {"name": ..., "arguments": "<json string>"}}]
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: Any = None  # the untouched provider payload, for when you need to debug

    @property
    def wants_tools(self) -> bool:
        """True when the model is asking you to run something. Chapter 2-3."""
        return bool(self.tool_calls)

    @property
    def truncated(self) -> bool:
        """True if the model was cut off by max_tokens. If this is True, treat `text` as
        incomplete — in particular, do not try to json.loads() it."""
        return self.finish_reason == "length"

    def as_message(self) -> Message:
        """The message you append to history so the model remembers what it said.

        When the model asked for tools, the tool_calls MUST be carried on this message.
        Drop them and the follow-up `role: tool` messages refer to a request that, as
        far as the model can see, it never made. Providers reject that outright.
        """
        content = self.text or (None if self.tool_calls else "")
        message: Message = {"role": "assistant", "content": content}
        if self.tool_calls:
            message["tool_calls"] = self.tool_calls
        return message


class LLMClient:
    """A minimal, provider-agnostic chat client.

    >>> client = LLMClient()
    >>> r = client.chat([{"role": "user", "content": "hi"}])
    >>> r.text
    'Hello! ...'
    """

    def __init__(
        self,
        model: str | None = None,
        *,
        api_key: str | None = None,
        base_url: str = OPENROUTER_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        from openai import OpenAI  # imported here so offline tests never need the SDK

        key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise errors.AuthError(
                "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout
        self._client = OpenAI(
            api_key=key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,  # we do our own retrying, in the open, where we can see it
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost"),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Agentic Course"),
            },
        )

    # ------------------------------------------------------------------ chat

    def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """One round trip. Raises an `agentlib.errors.LLMError` subclass on failure."""
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        try:
            raw = self._client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
        except Exception as exc:  # noqa: BLE001 - translate everything at the boundary
            raise _translate(exc) from exc

        choice = raw.choices[0]
        u = raw.usage
        calls = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.function.name, "arguments": c.function.arguments},
            }
            for c in (getattr(choice.message, "tool_calls", None) or [])
        ]
        return LLMResponse(
            text=choice.message.content or "",
            finish_reason=choice.finish_reason or "stop",
            tool_calls=calls,
            usage=Usage(
                prompt_tokens=getattr(u, "prompt_tokens", 0) or 0,
                completion_tokens=getattr(u, "completion_tokens", 0) or 0,
            ),
            model=raw.model,
            raw=raw,
        )

    # ---------------------------------------------------------------- stream

    def stream_raw(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Iterator[Any]:
        """Yield raw SDK chunks. Exercise 5 turns these into something usable."""
        try:
            stream = self._client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},  # ask for usage on the final chunk
                **kwargs,
            )
            yield from stream
        except Exception as exc:  # noqa: BLE001
            raise _translate(exc) from exc


def _translate(exc: Exception) -> errors.LLMError:
    """Turn an openai-SDK exception into one of ours."""
    if isinstance(exc, errors.LLMError):
        return exc

    status = getattr(exc, "status_code", None)
    if status is not None:
        return errors.classify_status(int(status), str(exc))

    name = type(exc).__name__
    if "Timeout" in name:
        return errors.TimeoutError(str(exc))
    if "Connection" in name:
        return errors.ConnectionError(str(exc))
    return errors.LLMError(f"{name}: {exc}")
