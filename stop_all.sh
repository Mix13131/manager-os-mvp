#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PID_DIR="data/pids"

web_pids="$(pgrep -f '/Users/tony/Projects/codex-workspace/manager_os_mvp/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000' || true)"
if [ -n "$web_pids" ]; then
  echo "$web_pids" | xargs kill
  echo "Stopped web PID(s): $web_pids"
else
  echo "web is not running"
fi

telegram_pids="$(pgrep -f '/Users/tony/Projects/codex-workspace/manager_os_mvp/.venv/bin/python -m app.telegram_bot' || true)"
if [ -n "$telegram_pids" ]; then
  echo "$telegram_pids" | xargs kill
  echo "Stopped telegram bot PID(s): $telegram_pids"
else
  echo "telegram is not running"
fi

rm -f "$PID_DIR/web.pid" "$PID_DIR/telegram.pid"
