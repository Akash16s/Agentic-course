"""Conversation state — the model is stateless, so this is the memory.

Promoted from Chapter 1, Exercise 2."""

from __future__ import annotations

from agentlib.llm import LLMResponse, Message

from agentlib.tokens import estimate_messages_tokens


class Conversation:
    def __init__(self, system: str | None = None) -> None:
        self._system = system
        self._messages: list[Message] = []

    # ------------------------------------------------------------ adding

    def add_message(self, role: str, content: str) -> "Conversation":
        if role == "system":
            raise ValueError(
                "use Conversation(system=...) or set_system(); a system message in the "
                "middle of a history is a bug, not a feature"
            )
        self._messages.append({"role": role, "content": content})
        return self

    def add_user(self, content: str) -> "Conversation":
        return self.add_message("user", content)

    def add_assistant(self, content: str) -> "Conversation":
        return self.add_message("assistant", content)

    def add_raw(self, message: Message) -> "Conversation":
        """Append a full message dict as-is.

        Needed from Chapter 2 on: assistant messages carry `tool_calls`, and tool
        messages carry `tool_call_id`. `add_message` only knows role + content.
        """
        if message.get("role") == "system":
            raise ValueError("system messages go through set_system()")
        self._messages.append(dict(message))
        return self

    def add_response(self, response: LLMResponse) -> "Conversation":
        """Append the model's reply, INCLUDING any tool calls it made."""
        return self.add_raw(response.as_message())

    def extend(self, messages: list[Message]) -> "Conversation":
        """Append several raw messages (e.g. a batch of tool results)."""
        for message in messages:
            self.add_raw(message)
        return self

    def set_system(self, content: str) -> "Conversation":
        self._system = content
        return self

    # ------------------------------------------------------------ reading

    @property
    def messages(self) -> list[Message]:
        out: list[Message] = []
        if self._system is not None:
            out.append({"role": "system", "content": self._system})
        # dict(m) copies each message, so a caller mutating the result cannot reach in
        out.extend(dict(m) for m in self._messages)
        return out

    @property
    def system(self) -> str | None:
        return self._system

    def __len__(self) -> int:
        return len(self._messages)

    def __repr__(self) -> str:
        return f"Conversation(system={self._system!r}, turns={len(self._messages)})"

    def last_assistant(self) -> str | None:
        for message in reversed(self._messages):
            if message["role"] == "assistant":
                return message["content"]
        return None

    def token_estimate(self) -> int:
        return estimate_messages_tokens(self.messages)

    # ------------------------------------------------------------ copying

    def copy(self) -> "Conversation":
        clone = Conversation(self._system)
        clone._messages = [dict(m) for m in self._messages]
        return clone

    # ------------------------------------------------------------ trimming

    def trim_to(self, max_tokens: int) -> int:
        dropped = 0
        while len(self._messages) > 1 and self.token_estimate() > max_tokens:
            self._messages.pop(0)
            dropped += 1
        return dropped
