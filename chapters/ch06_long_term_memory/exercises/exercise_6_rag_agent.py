"""EXERCISE 6 — An agent that remembers you between sessions.

No automated test. Needs an embedder (see the chapter's warning about OpenRouter).

    python chapters/ch06_long_term_memory/exercises/exercise_6_rag_agent.py

TASKS
  1. Pick an embedder:
       - HashingEmbedder            free, offline, lexical only
       - APIEmbedder                OpenAI key, text-embedding-3-small
       - sentence-transformers      pip install, all-MiniLM-L6-v2, free + semantic
     Wrap whichever you choose in CachedEmbedder.

  2. Build a `MemoryAgent`:
       - before each run: `memories = store.recall(user_message, subject=user_id)`
         and inject `store.as_context(memories)` into the system prompt
       - give the agent two tools:
             remember(fact: str, kind: str, importance: float) -> str
             search_memory(query: str) -> str
         so it can write and read deliberately, not just implicitly
       - after each run: `extract_memories(transcript, call_model)` and store what
         comes back

  3. Prove it works across sessions: run once telling it three things about yourself,
     kill the process, run again and ask it what it knows.

  4. THEN INVESTIGATE — this is where the learning is:
       a. Compare HashingEmbedder with a real embedder on the SAME store. Ask
          "what language do I like?" after storing "Akash prefers Python". Lexical
          search fails; semantic search works. Feel the difference.
       b. Turn dedup off (`dedup_threshold=2.0`). Have a 20-turn conversation.
          Count the memories. Then recall something and look at how much of the
          top-5 is duplicates.
       c. Store 200 junk memories alongside 5 real ones. Does recall still find the
          real ones? This is the "remember everything" failure, reproduced.
       d. Set `w_recency=0.0` and re-run a query where you have deliberately
          contradicted yourself. Watch the stale fact win.
       e. Time `recall()` with 100, 1,000 and 10,000 memories. Plot it. You should
          see the O(n) line that tells you when to switch to pgvector.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
