#!/usr/bin/env bash
# Course helper.
#
#   ./run_tests.sh                 every chapter
#   ./run_tests.sh 1               just chapter 1
#   ./run_tests.sh 1 tokens        just exercise 1 of chapter 1
#   ./run_tests.sh --solutions 6   run chapter 6 against the SOLUTIONS (to check
#                                  whether a failure is yours or the course's)
set -euo pipefail
cd "$(dirname "$0")"
PY=./.venv/bin/python

if [[ "${1:-}" == "--solutions" ]]; then
  shift
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  rsync -a --exclude .venv --exclude __pycache__ --exclude .pytest_cache ./ "$tmp/"
  for d in "$tmp"/chapters/*/; do
    for f in "$d"solutions/exercise_*.py; do
      [ -e "$f" ] || continue
      cp "$f" "$d/exercises/$(basename "$f")"
    done
  done
  cd "$tmp"
  PY="$OLDPWD/.venv/bin/python"
fi

if [[ $# -eq 0 ]]; then
  exec "$PY" -m pytest chapters -q
fi
# Accept "6" or "6b" (bonus chapters are numbered like ch06b_retrieval).
num="${1%%[a-z]*}"; suffix="${1#$num}"
target="$(echo chapters/ch$(printf '%02d' "$num")${suffix}_*)"
if [[ $# -ge 2 ]]; then
  exec "$PY" -m pytest "$target/tests" -q -k "$2"
fi
exec "$PY" -m pytest "$target/tests" -q
