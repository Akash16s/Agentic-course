"""EXERCISE 5 — A real MCP server, and a real third-party one.

No automated test. Parts 1-3 are offline; part 4 needs your key.

    python chapters/ch16_mcp/exercises/exercise_5_real_mcp.py

PART 1 — write a server and run it as a subprocess
  Create `course_server.py` exposing, over this course directory:
      tools:     search_chapters(query), read_chapter(number), count_exercises()
      resources: course://readme, course://progress
      prompts:   explain_chapter(number)
  Run it with `subprocess_transport(["python", "course_server.py"])` and drive it
  from a client. Confirm the handshake, tools/list and tools/call all work.

PART 2 — break it on purpose, three ways
  Each of these is a real failure you will meet. Produce it, read the error, and
  fix it, so you recognise it instantly next time.
    a. Add `print("starting up")` at the top of the server. What does the client
       report? Is the message anywhere near the cause?
    b. Remove the `flush()` after writing a reply. What does the client do?
    c. Make the server raise on a malformed line instead of skipping. Send it one
       blank line from a shell pipe.
  Then fix all three and confirm it survives garbage input.

PART 3 — bridge it into an agent
  a. `bridge_tools(client, prefix="course_")`, put it in a ToolRegistry, and run
     your Chapter 3 agent on "how many exercises are in chapter 6?".
  b. Add a SECOND server with a tool also called `search`. Confirm the unprefixed
     version raises on the duplicate, and the prefixed one does not.
  c. Add Chapter 12 tracing. Are the MCP round trips visible as spans? Add the
     span if not — you want the protocol overhead in the trace, because it is
     real and it is invisible otherwise.
  d. Add a Chapter 14 PermissionPolicy over the bridged tools. Confirm a denied
     remote tool returns a tool result, not an exception.

PART 4 — a third-party server
  Install any published MCP server (the filesystem one is a good first choice)
  and connect to it with YOUR client, not with a vendor SDK.
    a. Does your handshake work? If not, which field did you get wrong?
    b. Read its tool descriptions. They are about to enter your model's context —
       would you have written them that way?
    c. Consider: what filesystem and network access does that process have right
       now? Write down what you would do before running one you had not read.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


def main() -> None:
    raise NotImplementedError


if __name__ == "__main__":
    main()
