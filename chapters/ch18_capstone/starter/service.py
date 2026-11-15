"""Requirement 15: the HTTP service.

    uvicorn service:app --reload
"""

from __future__ import annotations

# TODO
# POST /runs                 -> 202 {"run_id"}
# GET  /runs/{id}            -> the run
# GET  /runs/{id}/stream     -> SSE, with a [DONE] sentinel and an error event
# GET  /runs?session_id=...  -> recent runs for a session
# POST /runs/{id}/cancel
# GET  /healthz              -> {"ok", "queue_depth"}
#
# Must survive a restart: reclaim_stale() on startup (ch 15).
# Must check that THIS session owns THIS run before returning it (ch 14, ch 15).
