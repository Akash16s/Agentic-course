# Capstone starter

Copy this directory to a new folder OUTSIDE `chapters/` — somewhere like
`~/Desktop/Learning/capstone/` — and build there. Keeping it out of the course
tree means you can `git init` it and treat it as a real project.

```bash
cp -r chapters/ch18_capstone/starter ~/Desktop/Learning/capstone
cd ~/Desktop/Learning/capstone
```

Then point the acceptance suite at it:

```bash
CAPSTONE_PATH=~/Desktop/Learning/capstone \
  pytest "chapters/ch18_capstone/tests" -q
```

The suite checks STRUCTURE — that the pieces exist and connect. It cannot tell you
whether your agent is any good. That is what `evals/` is for, and writing it is
most of the point.

## What each file is for

| File | Requirement |
|---|---|
| `agent.py` | the agent, tools, prompts (ch 1-9, 13, 14) |
| `service.py` | HTTP: submit, poll, stream (ch 15) |
| `mcp_server.py` | your MCP surface (ch 16) |
| `evals/dataset.jsonl` | >= 30 cases, >= 5 negative (ch 10) |
| `evals/checks.py` | assertions, judge, trajectory (ch 10, 11) |
| `evals/run.py` | the runner and the CI gate (ch 10) |
| `DECISIONS.md` | requirements 7, 8, 17 — with numbers |
| `RESULTS.md` | the numbers, including one regression |
