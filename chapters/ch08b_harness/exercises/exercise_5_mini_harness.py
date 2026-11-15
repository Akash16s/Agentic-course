"""EXERCISE 5 — A mini harness, on a real model.

No automated test. Needs your key. Costs a few cents. The TRACE is the exercise.

    python chapters/ch08b_harness/exercises/exercise_5_mini_harness.py

TASKS
  1. Build one agent with everything from this chapter:
       - todos     : a TodoList, its todo_write tool, and the client wrapped in
                     TodoReminderClient so the list is re-injected every turn
       - skills    : make a folder `my_skills/` (anywhere outside the repo is fine)
                     with two skills:
                       chapter-audit  "How to audit a course chapter. Use when asked
                                       to check a chapter's exercises and tests."
                                      body: the steps — list exercises/, list tests/,
                                      count `def test_` per file, note mismatches
                       report-style   "House style for written reports. Use before
                                       writing any report or summary file."
                                      body: headings, a table, max 200 words
                     put registry.index_prompt() in the system prompt and give the
                     agent load_skill_tool(registry)
       - workspace : Workspace(<a temp dir>) and its four tools, for notes and the
                     final report
       - subagents : a SubagentRunner whose pool is two READ-ONLY tools sandboxed
                     to the course root — list_files(directory) and
                     read_file(path) (use agentlib.security.sandbox_path) — and give
                     the parent runner.as_tool(). The parent itself gets NO direct
                     read_file: it has to delegate to read the course.
       - offload   : wrap read_file with offloading_tool(...) so a big file cannot
                     flood a subagent's window either
     Task:
       "Audit chapters 3 and 8 of the course at <root>. For each, find how many
        exercises and how many tests it has, and whether every tested exercise has
        a solution. Save findings to notes/ as you go, then write report.md."

  2. Print a trace as it runs. Pass `on_step=` a callback that prints, per step:
         step | tools called | parent tokens so far | todo progress (e.g. 2/5)
     And print each SubagentResult as it arrives (SubagentRunner(on_result=...)).

  3. At the end print:
         - result.stop_reason, result.tool_sequence
         - parent cost, runner.total_cost, and the TOTAL. Subagents are not free.
         - todo_list.render()
         - registry.loaded  (which skills did it actually load?)
         - workspace.list_notes() and the contents of report.md

  4. Add a hook (README §9). Wrap the parent's registry in a HookedRegistry with:
         - a PRE hook that blocks write_note to anything outside notes/ or
           report.md, returning a message the model can act on
         - a POST hook that prints tool name, duration and result size
     Run again. Did the model ever trip the policy? What did it do next?

  5. NOW EXPERIMENT — write down the numbers:
       a. Remove TodoReminderClient (keep the tool). Does the model still update
          the list? How many todo_write calls with vs without the reminder?
       b. Give the parent read_file directly and remove delegate. Compare the
          parent's peak prompt tokens and the total cost with the delegated run.
          Which won on THIS task? Example 01 predicts the answer — was it right?
       c. Make the chapter-audit description vague ("Chapter stuff."). Does the
          model still load it?
       d. Set the subagent max_steps=2. Does the parent notice the
          "[subagent stopped early: ...]" prefix and re-delegate, or does it
          write the report anyway?
       e. If your model supports it, pass reasoning effort through
          (`LLMClient.chat(..., extra_body={"reasoning": {"effort": "low"}})` — wrap
          the client to add it). Compare steps, cost and wall-clock at low vs high.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.llm import LLMClient
from agentlib.security import sandbox_path
from agentlib.tools import ToolRegistry, tool

# TODO: import your pieces from exercises 1-4 (or agentlib.harness for the reference)
# from agentlib.agent import Agent

COURSE_ROOT = Path(__file__).resolve().parents[3]


def main() -> None:
    # TODO 1: the read-only course tools (list_files, read_file), sandboxed to COURSE_ROOT
    # TODO 2: TodoList + todo_write_tool + TodoReminderClient(LLMClient(), todos)
    # TODO 3: SkillRegistry("my_skills") + load_skill_tool; index in the system prompt
    # TODO 4: Workspace(tmp dir) + its tools
    # TODO 5: SubagentRunner(LLMClient(), ToolRegistry([list_files, offloading read_file]))
    # TODO 6: agent = Agent(wrapped_client, tools=..., system=..., max_steps=30,
    #                       budget_usd=0.50, on_step=...)
    # TODO 7: run, then print the trace, costs, todos, loaded skills and report.md
    raise NotImplementedError


if __name__ == "__main__":
    main()
