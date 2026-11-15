"""Fakes, so the whole test suite runs offline and free.

This is not a testing luxury, it is the reason you can have an eval suite at all
(Chapters 10-11). Any code that talks to a model must be injectable with a fake, or you
cannot test it without paying and without flakiness.

`FakeLLMClient` is a drop-in for `LLMClient`: same `chat()` signature, scripted results,
and it records every call so you can assert on what your code actually sent.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

from agentlib.llm import LLMResponse, Message, Usage


def tool_call(name: str, arguments: dict[str, Any] | str = "{}", call_id: str | None = None):
    """Build one provider-shaped tool-call dict, for scripting fakes.

    >>> tool_call("add", {"a": 1, "b": 2})["function"]["name"]
    'add'
    """
    import json as _json

    if not isinstance(arguments, str):
        arguments = _json.dumps(arguments)
    return {
        "id": call_id or f"call_{abs(hash((name, arguments))) % 10**8}",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def tool_response(*calls: dict[str, Any], text: str = "", usage: Usage | None = None):
    """An LLMResponse that asks for tools, for scripting fakes.

    >>> r = tool_response(tool_call("add", {"a": 1}))
    >>> r.wants_tools
    True
    """
    return LLMResponse(
        text=text,
        finish_reason="tool_calls",
        tool_calls=list(calls),
        usage=usage or Usage(10, 5),
        model="fake/model",
    )


class FakeLLMClient:
    """A scripted stand-in for `LLMClient`.

    Each item in `script` is either:
      * an `LLMResponse`     -> returned
      * an `Exception`       -> raised
      * a `str`              -> wrapped in a default LLMResponse

    >>> c = FakeLLMClient(["hello"])
    >>> c.chat([{"role": "user", "content": "hi"}]).text
    'hello'
    >>> c.call_count
    1
    """

    def __init__(
        self,
        script: Iterable[LLMResponse | Exception | str] | None = None,
        *,
        model: str = "fake/model",
        default_usage: Usage = Usage(10, 5),
    ) -> None:
        self.model = model
        self.default_usage = default_usage
        self._script: list[Any] = list(script or [])
        #: every (messages, kwargs) pair this client was called with
        self.calls: list[tuple[list[Message], dict[str, Any]]] = []

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_messages(self) -> list[Message]:
        return self.calls[-1][0]

    def chat(self, messages: list[Message], **kwargs: Any) -> LLMResponse:
        # store a *copy*: if the caller mutates its list afterwards, our record must not change
        self.calls.append(([dict(m) for m in messages], dict(kwargs)))

        if not self._script:
            return LLMResponse(
                text=f"fake reply #{self.call_count}",
                usage=self.default_usage,
                model=self.model,
            )

        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, LLMResponse):
            return item
        return LLMResponse(text=str(item), usage=self.default_usage, model=self.model)

    def stream_raw(self, messages: list[Message], **kwargs: Any) -> Iterator[Any]:
        """Yields objects shaped like OpenAI stream chunks, so Exercise 5 can be tested
        without a network. Splits the scripted text into word-sized deltas."""
        response = self.chat(messages, **kwargs)
        words = response.text.split(" ")
        for i, word in enumerate(words):
            piece = word if i == 0 else " " + word
            yield _FakeChunk(delta_content=piece)
        yield _FakeChunk(finish_reason=response.finish_reason)
        yield _FakeChunk(usage=response.usage)


# --- minimal objects that quack like the OpenAI streaming payloads -------------------


class _FakeDelta:
    def __init__(self, content: str | None = None) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str | None = None, finish_reason: str | None = None) -> None:
        self.delta = _FakeDelta(content)
        self.finish_reason = finish_reason


class _FakeUsage:
    def __init__(self, usage: Usage) -> None:
        self.prompt_tokens = usage.prompt_tokens
        self.completion_tokens = usage.completion_tokens
        self.total_tokens = usage.total_tokens


class _FakeChunk:
    def __init__(
        self,
        delta_content: str | None = None,
        finish_reason: str | None = None,
        usage: Usage | None = None,
    ) -> None:
        self.choices = (
            [_FakeChoice(delta_content, finish_reason)]
            if (delta_content is not None or finish_reason is not None)
            else []
        )
        self.usage = _FakeUsage(usage) if usage is not None else None
        self.model = "fake/model"
