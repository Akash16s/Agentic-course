"""EXERCISE 2 — The Conversation object.

WHY: The model is stateless, so state is YOUR job. Every agent framework has this class
under some name (`MessageHistory`, `Thread`, `ChatState`, `checkpoint`). Building it
yourself means you will never again be confused about where a message came from.

Three design decisions here are worth internalising, because you will meet them again in
every serious codebase:

  1. **The system prompt is special.** It is always first and is never trimmed away.
     Lose it and your agent forgets its own identity and rules mid-conversation.
  2. **`messages` returns a COPY.** Callers must not be able to reach in and mutate your
     internal list. Half the "why did my history get corrupted" bugs are this.
  3. **`copy()` gives a real fork.** Essential later for speculative branches, retries
     and multi-agent handoffs (Chapters 7-8).

Run the tests:
    pytest chapters/ch01_agent_loop/tests -q -k conversation
"""

from __future__ import annotations

from agentlib.llm import LLMResponse, Message

from .exercise_1_tokens import estimate_messages_tokens


class Conversation:
    """Mutable, ordered chat history with a protected system prompt.

    >>> c = Conversation("You are terse.")
    >>> c.add_user("hi").add_assistant("hello")
    >>> len(c)
    2
    >>> c.messages[0]["role"]
    'system'
    """

    def __init__(self, system: str | None = None) -> None:
        """Store the system prompt (if given) and set up internal state.

        Suggested internals:
            self._system: str | None
            self._messages: list[Message]   # NOT including the system message
        """
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------ adding

    def add_message(self, role: str, content: str) -> "Conversation":
        """Append a message and return self, so calls can be chained.

        Raise ValueError if role == "system" — the system prompt is set in __init__ or
        via `set_system`, never appended. (Stray system messages mid-history are a real
        and confusing bug: some providers error, others silently ignore them.)
        """
        # TODO: implement
        raise NotImplementedError

    def add_user(self, content: str) -> "Conversation":
        """Convenience for add_message("user", content)."""
        # TODO: implement
        raise NotImplementedError

    def add_assistant(self, content: str) -> "Conversation":
        """Convenience for add_message("assistant", content)."""
        # TODO: implement
        raise NotImplementedError

    def add_response(self, response: LLMResponse) -> "Conversation":
        """Append an `LLMResponse` as an assistant message.

        This is the one you will call in the agent loop. Forgetting it is Common
        Mistake #1 from the chapter: the model then never sees what it just said, and
        repeats itself forever.
        """
        # TODO: implement
        raise NotImplementedError

    def set_system(self, content: str) -> "Conversation":
        """Replace the system prompt without touching the rest of the history."""
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------ reading

    @property
    def messages(self) -> list[Message]:
        """The full list to send to the API: system first (if any), then the rest.

        MUST return a new list of new dicts. Mutating the result must not affect this
        Conversation.
        """
        # TODO: implement
        raise NotImplementedError

    @property
    def system(self) -> str | None:
        # TODO: implement
        raise NotImplementedError

    def __len__(self) -> int:
        """Number of NON-system messages. (The system prompt is configuration, not
        conversation.)"""
        # TODO: implement
        raise NotImplementedError

    def last_assistant(self) -> str | None:
        """Content of the most recent assistant message, or None if there isn't one."""
        # TODO: implement
        raise NotImplementedError

    def token_estimate(self) -> int:
        """Estimated prompt tokens for `self.messages`, via Exercise 1."""
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------ copying

    def copy(self) -> "Conversation":
        """A deep-enough copy: mutating either conversation must not affect the other."""
        # TODO: implement
        raise NotImplementedError

    # ------------------------------------------------------------ trimming

    def trim_to(self, max_tokens: int) -> int:
        """Drop the OLDEST non-system messages until the estimate fits. Return how many
        were dropped.

        Rules:
          * never drop the system prompt
          * never drop the last remaining non-system message (an empty conversation is
            useless; better to send something too big and get a clear API error than to
            silently send nothing)
          * drop from the front — recent context matters more than ancient context

        This is the crudest possible strategy and it loses information permanently.
        Chapter 5 replaces it with rolling summarisation. Feel its bluntness now.

        >>> c = Conversation()
        >>> for i in range(10): c.add_user("x" * 100)
        >>> dropped = c.trim_to(50)
        >>> dropped > 0
        True
        """
        # TODO: implement
        raise NotImplementedError
