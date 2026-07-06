#!/usr/bin/env bash
# LangOps end-to-end smoke test (Phase 4 / M4 acceptance).
#
# Brings up the full Docker Compose stack, runs examples/simple-agent on the
# host, and verifies the execution flows SDK → Collector → API → Postgres and
# is queryable. Then a resilience check: kill the API mid-stream and confirm
# the Collector's retry queue delivers the spans once it comes back.
#
# Requirements: Docker Desktop running, Python 3.12, bash (git-bash/WSL on
# Windows). Run from the repo root:  bash scripts/e2e-smoke.sh
# Set KEEP_UP=1 to leave the stack running afterwards.

set -euo pipefail
cd "$(dirname "$0")/.."

API=http://localhost:8000
VENV=.e2e-venv
step() { printf '\n\033[1;36m==> %s\033[0m\n' "$1"; }
fail() { printf '\033[1;31mFAIL: %s\033[0m\n' "$1" >&2; exit 1; }

# Resolve a venv python across Windows (Scripts) and Unix (bin).
pybin() { [ -x "$VENV/bin/python" ] && echo "$VENV/bin/python" || echo "$VENV/Scripts/python"; }

wait_for_health() {
  step "Waiting for the API to become healthy"
  for _ in $(seq 1 60); do
    if curl -sf "$API/api/v1/health" >/dev/null 2>&1; then echo "API healthy."; return 0; fi
    sleep 2
  done
  fail "API did not become healthy in time"
}

# $1 = expected minimum execution count
assert_executions() {
  "$(pybin)" - "$1" <<'PY'
import json, sys, time, urllib.request
minimum = int(sys.argv[1])
deadline = time.time() + 30
while time.time() < deadline:
    with urllib.request.urlopen("http://localhost:8000/api/v1/executions") as r:
        data = json.load(r)
    if data["total"] >= minimum:
        ex = data["items"][0]
        detail_url = f"http://localhost:8000/api/v1/executions/{ex['id']}"
        with urllib.request.urlopen(detail_url) as r:
            detail = json.load(r)
        print(f"  executions={data['total']} status={ex['status']} "
              f"nodes={len(detail['nodes'])} cost={ex['total_cost']}")
        assert detail["nodes"], "execution has no node rows"
        sys.exit(0)
    time.sleep(2)
print(f"  timed out: only saw < {minimum} executions", file=sys.stderr)
sys.exit(1)
PY
}

step "Building and starting the stack"
docker compose up -d --build
trap '[ "${KEEP_UP:-0}" = "1" ] || docker compose down' EXIT

wait_for_health

step "Installing the SDK into a throwaway venv"
python -m venv "$VENV"
"$(pybin)" -m pip install -q --upgrade pip
"$(pybin)" -m pip install -q -e ./sdk

step "Run 1: exercise the pipeline"
"$(pybin)" examples/simple-agent/main.py
assert_executions 1 || fail "execution did not reach the query API"

step "Resilience: kill the API, emit while it's down, restart"
docker compose stop api
"$(pybin)" examples/simple-agent/main.py   # Collector queues spans while API is down
docker compose start api
wait_for_health
# The queued run plus the first one → at least 2 executions, no data lost.
assert_executions 2 || fail "Collector did not replay spans after API restart"

step "PASS — end-to-end pipeline verified"
echo "Dashboard: http://localhost:3000   API docs: $API/docs"
