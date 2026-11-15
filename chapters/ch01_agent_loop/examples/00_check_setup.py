"""Run me first. Verifies your key, shows your credit, lists usable models.

    python chapters/ch01_agent_loop/examples/00_check_setup.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # so `agentlib` imports

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

KEY = os.getenv("OPENROUTER_API_KEY")
BASE = "https://openrouter.ai/api/v1"


def main() -> None:
    if not KEY:
        print("X  OPENROUTER_API_KEY not found.")
        print("   cp .env.example .env   and paste your key in.")
        sys.exit(1)
    print(f"key found: {KEY[:12]}...{KEY[-4:]}\n")

    headers = {"Authorization": f"Bearer {KEY}"}

    # 1. credit -------------------------------------------------------------
    r = httpx.get(f"{BASE}/key", headers=headers, timeout=20)
    if r.status_code != 200:
        print(f"X  key rejected ({r.status_code}): {r.text[:200]}")
        sys.exit(1)
    data = r.json().get("data", {})
    used, limit = data.get("usage"), data.get("limit")
    print(f"credit used : ${used}")
    print(f"credit limit: {'unlimited' if limit is None else f'${limit}'}\n")

    # 2. the model in your .env --------------------------------------------
    want = os.getenv("AGENT_MODEL", "anthropic/claude-haiku-4.5")
    models = httpx.get(f"{BASE}/models", timeout=30).json()["data"]
    by_id = {m["id"]: m for m in models}
    if want in by_id:
        print(f"AGENT_MODEL '{want}' is live.\n")
    else:
        print(f"!  AGENT_MODEL '{want}' NOT FOUND. Pick one from the list below and")
        print("   update .env.\n")

    # 3. cheap, tool-capable options ---------------------------------------
    def price(m, kind):
        try:
            return float(m["pricing"][kind]) * 1_000_000
        except (KeyError, TypeError, ValueError):
            return float("inf")

    candidates = [
        m
        for m in models
        if "tools" in (m.get("supported_parameters") or [])
        and price(m, "prompt") < 2.0
        and price(m, "prompt") > 0
    ]
    candidates.sort(key=lambda m: price(m, "prompt"))

    print(f"{'model id':<48} {'$/M in':>8} {'$/M out':>9} {'context':>9}")
    print("-" * 78)
    for m in candidates[:20]:
        print(
            f"{m['id']:<48} {price(m,'prompt'):>8.2f} {price(m,'completion'):>9.2f} "
            f"{m.get('context_length', 0):>9,}"
        )
    print(f"\n({len(models)} models total, {len(candidates)} cheap + tool-capable)")
    print("\nTip: develop on a cheap one. Save the expensive model for quality comparisons.")


if __name__ == "__main__":
    main()
