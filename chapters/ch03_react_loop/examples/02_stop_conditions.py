"""Every stop reason, triggered on purpose. Free and offline.

    python chapters/ch03_react_loop/examples/02_stop_conditions.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib import errors
from agentlib.agent import Agent, StopReason
from agentlib.errors import StopSignal
from agentlib.testing import FakeLLMClient, tool_call, tool_response
from agentlib.tools import ToolRegistry, tool


@tool
def spin(n: int) -> str:
    """Does nothing useful."""
    return "no results"


@tool
def submit_answer(answer: str) -> str:
    """Submit the final answer and finish."""
    raise StopSignal(answer)


REG = ToolRegistry([spin, submit_answer])
LOOP = [tool_response(tool_call("spin", {"n": 1}))] * 50


class FakeClock:
    def __init__(self, step):
        self.now, self.step = 0.0, step

    def __call__(self):
        self.now += self.step
        return self.now


scenarios = {
    "DONE":      lambda: Agent(FakeLLMClient(["Here is the answer."])).run("q"),
    "STOP_TOOL": lambda: Agent(
        FakeLLMClient([tool_response(tool_call("submit_answer", {"answer": "42"}))]),
        tools=REG,
    ).run("q"),
    "MAX_STEPS": lambda: Agent(FakeLLMClient(LOOP), tools=REG, max_steps=5).run("q"),
    "BUDGET":    lambda: Agent(
        FakeLLMClient(LOOP), tools=REG, max_steps=50, budget_usd=0.0005
    ).run("q"),
    "TIMEOUT":   lambda: Agent(
        FakeLLMClient(LOOP), tools=REG, max_steps=50, timeout_s=2.0,
        clock=FakeClock(0.5),
    ).run("q"),
    "ERROR":     lambda: Agent(
        FakeLLMClient([errors.ServerError("503")] * 10), max_attempts=1
    ).run("q"),
}

print(f"{'reason':<12} {'steps':>6} {'cost':>9} {'ok':>4}  output / error")
print("-" * 78)
for label, run in scenarios.items():
    r = run()
    detail = r.error or r.output or "(nothing)"
    print(f"{r.stop_reason.value:<12} {r.step_count:>6} {r.cost:>9.5f} "
          f"{str(r.succeeded):>5}  {detail[:34]}")

print("-" * 78)
print("""
Note the `ok` column. MAX_STEPS, BUDGET and TIMEOUT all produced *something* — but
they were cut off. Treating a cut-off run as a success is how a confident partial
answer reaches a user. `succeeded` is True for DONE and STOP_TOOL only.

Also note: BUDGET still reports the cost. The money left your account whether or not
you report it, and the report is the only way anyone finds out.
""")
