#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PID_DIR="data/pids"

web_pids="$(pgrep -f '/Users/tony/Projects/codex-workspace/manager_os_mvp/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000' || true)"
if [ -n "$web_pids" ]; then
  echo "web: running (PID(s) $web_pids)"
else
  echo "web: stopped"
fi

telegram_pids="$(pgrep -f '/Users/tony/Projects/codex-workspace/manager_os_mvp/.venv/bin/python -m app.telegram_bot' || true)"
if [ -n "$telegram_pids" ]; then
  echo "telegram: running (PID(s) $telegram_pids)"
else
  echo "telegram: stopped"
fi
