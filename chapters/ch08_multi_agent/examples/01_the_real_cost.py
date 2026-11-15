"""What multi-agent actually costs, and what it actually buys. Free and offline.

    python chapters/ch08_multi_agent/examples/01_the_real_cost.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from agentlib.multiagent import Orchestrator, synthesis_prompt
from agentlib.pricing import cost_usd

MODEL = "anthropic/claude-sonnet-4.5"
SUBTASKS = 4
WORKER_LATENCY = 1.2          # seconds per subtask
SYSTEM_TOKENS = 600           # per agent: its own prompt + tool schemas
WORK_TOKENS = 2_500           # context each subtask actually needs
OUTPUT_TOKENS = 400

print("=" * 72)
print("COST")
print("=" * 72)

single_in = SYSTEM_TOKENS + SUBTASKS * WORK_TOKENS
single_out = OUTPUT_TOKENS
single = cost_usd(MODEL, single_in, single_out)

planner = cost_usd(MODEL, SYSTEM_TOKENS + 200, 300)
workers = SUBTASKS * cost_usd(MODEL, SYSTEM_TOKENS + WORK_TOKENS, OUTPUT_TOKENS)
synth = cost_usd(MODEL, 300 + SUBTASKS * OUTPUT_TOKENS, OUTPUT_TOKENS)
multi = planner + workers + synth

print(f"{'':<22} {'in tok':>9} {'$':>9}")
print("-" * 44)
print(f"{'single agent':<22} {single_in:>9,} {single:>9.4f}")
print(f"{'  planner':<22} {SYSTEM_TOKENS + 200:>9,} {planner:>9.4f}")
print(f"{'  4 workers':<22} {SUBTASKS * (SYSTEM_TOKENS + WORK_TOKENS):>9,} {workers:>9.4f}")
print(f"{'  synthesiser':<22} {300 + SUBTASKS * OUTPUT_TOKENS:>9,} {synth:>9.4f}")
print(f"{'multi-agent TOTAL':<22} {'':>9} {multi:>9.4f}")
print(f"\nratio: {multi / single:.2f}x")
print("""
The extra is not waste exactly — it is what you pay for separation. Each worker
re-pays for its own system prompt and tool schemas, the planner pays to split the
task, and the synthesiser pays to read everything back. None of those exist in the
single-agent version.""")

print("\n" + "=" * 72)
print("WALL CLOCK — this is the thing you are actually buying")
print("=" * 72)


def worker(task):
    time.sleep(WORKER_LATENCY)
    return f"findings for {task}"


tasks = [(f"w{i}", f"subtask {i}") for i in range(SUBTASKS)]
workers_map = {f"w{i}": worker for i in range(SUBTASKS)}

t0 = time.monotonic()
Orchestrator(workers_map, max_parallel=1).fan_out(tasks)
serial = time.monotonic() - t0

t0 = time.monotonic()
results = Orchestrator(workers_map, max_parallel=SUBTASKS).fan_out(tasks)
parallel = time.monotonic() - t0

print(f"  serial   (one agent, {SUBTASKS} subtasks one after another): {serial:.2f}s")
print(f"  parallel ({SUBTASKS} workers at once)                      : {parallel:.2f}s")
print(f"  speedup  : {serial / parallel:.1f}x")
print(f"""
  So the honest trade for this shape of task is:
      {multi / single:.1f}x the cost, {serial / parallel:.1f}x faster.

  That is a good deal when a human is waiting and a bad deal in a batch job.
  Which one you are building is the question to answer BEFORE you pick a pattern,
  not after.""")

print("\n" + "=" * 72)
print("THE FAILURE THE SYNTHESISER MUST SEE")
print("=" * 72)
broken = Orchestrator({**workers_map, "w2": lambda t: (_ for _ in ()).throw(
    RuntimeError("rate limited"))}, max_parallel=4).fan_out(tasks)

prompt = synthesis_prompt("compare the four options", broken)
print(prompt[prompt.index("--- w2 ---"):prompt.index("--- w3 ---")])
print("""If that "[FAILED: ...]" line were missing, the synthesiser would have three
findings and a goal mentioning four options — and it would write the fourth
paragraph anyway. The answer would look complete. Nothing would error.

That is the most common bug in this pattern, and the reason synthesis_prompt
includes failures instead of filtering them out.""")
