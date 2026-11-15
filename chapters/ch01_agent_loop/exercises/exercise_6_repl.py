"""EXERCISE 6 — Put it together: a real CLI chat.

This is the integration exercise. It uses ALL of exercises 1-5 and it talks to the real
API, so finish those first. There is no automated test — the test is that it works and
that you understand every line.

    python chapters/ch01_agent_loop/exercises/exercise_6_repl.py

Commands to support:
    /cost     show the cost report
    /history  show the message list actually being sent
    /tokens   show the current estimated prompt size
    /trim N   trim history to N tokens
    /reset    start over
    /quit     exit

WHAT TO NOTICE WHILE USING IT (this is the actual learning):
  * watch `prompt_tokens` climb every single turn, even when you say "hi"
  * watch the per-turn cost climb with it
  * type /history after a few turns and see YOUR list — that is the entire memory
  * /trim to something small, then ask about the first thing you said. Watch it forget.
    That is the crude version of the problem Chapters 4-6 solve properly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib import errors
from agentlib.llm import LLMClient
from chapters.ch01_agent_loop.exercises.exercise_2_conversation import Conversation
from chapters.ch01_agent_loop.exercises.exercise_3_retry import chat_with_retry
from chapters.ch01_agent_loop.exercises.exercise_4_cost import CostTracker
from chapters.ch01_agent_loop.exercises.exercise_5_stream import stream_chat

# Note the import path. Chapter folders are named `ch01_agent_loop` rather than
# `01-the-agent-loop` for one boring but important reason: Python module names cannot
# start with a digit or contain hyphens. Every chapter is a real package, so exercises
# can import each other and pytest can find everything without sys.path hacks.

SYSTEM_PROMPT = "You are a concise, helpful assistant. Answer in 3 sentences or fewer."


def main() -> None:
    # TODO 1: build an LLMClient and a Conversation(SYSTEM_PROMPT)
    # TODO 2: build a CostTracker with a small budget, e.g. budget_usd=0.25,
    #         so a mistake cannot cost you real money
    # TODO 3: loop:
    #           - read input()
    #           - handle the / commands
    #           - otherwise: conversation.add_user(text)
    #           - call your stream_chat via chat_with_retry so you get BOTH
    #             streaming and resilience
    #             (think: what does chat_with_retry need from the thing it calls?
    #              You may need a tiny adapter. That question is the point of this step.)
    #           - conversation.add_response(response)
    #           - tracker.record(response)
    #           - print a status line: tokens in/out, this turn's cost, running total
    # TODO 4: catch errors.BudgetExceeded and stop cleanly
    # TODO 5: catch KeyboardInterrupt and exit without a traceback
    raise NotImplementedError


if __name__ == "__main__":
    main()
