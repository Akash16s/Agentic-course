"""EXERCISE 5 — A multi-session stateful chat.

No automated test. Needs your key.

    python chapters/ch05_short_term_memory/exercises/exercise_5_service.py

TASKS
  1. Build a `ChatService` with `send(session_id, text) -> str` that:
       a. loads the session from a SQLiteSessionStore
       b. appends the user message
       c. runs `strategy.build(session.messages)` to get the model's view
       d. calls the model, appends the reply, saves
       e. returns the reply
     Note that (b) and (d) write the FULL record, while (c) only builds the view.
     If you find yourself saving the trimmed list, stop and re-read section 1.

  2. A CLI with `/session <id>` to switch threads. Prove that:
       - two sessions have independent histories
       - killing the process and restarting keeps both

  3. Use SummaryBuffer with a CHEAP model for `summarise` and your normal model for
     the chat. Print every summarisation as it happens.

  4. THEN MEASURE — this is the exercise:
       a. Have a 30-turn conversation. Count how many summarisation calls happened.
          Now remove the threshold check so it summarises every turn. Count again,
          and compare total cost. The ratio is the point.
       b. After two compactions, ask about something you said in turn 2. Does it
          survive? Now delete the carry-forward and repeat. Watch it vanish.
       c. Open the .db file with `sqlite3 sessions.db "select * from sessions"`.
          Confirm the FULL history is there, not the trimmed view.
       d. Run two copies of the script at once against the same session and interleave
          messages. Find the lost update.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.llm import LLMClient


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
