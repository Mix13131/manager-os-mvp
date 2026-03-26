#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PID_DIR="data/pids"
LOG_DIR="data/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

./.venv/bin/pip install -r requirements.txt >/dev/null

existing_web_pid="$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
existing_bot_pid="$(pgrep -f '/Users/tony/Projects/codex-workspace/manager_os_mvp/.venv/bin/python -m app.telegram_bot' | head -n 1 || true)"

if [ -n "$existing_web_pid" ] && kill -0 "$existing_web_pid" 2>/dev/null; then
  echo "$existing_web_pid" >"$PID_DIR/web.pid"
  echo "Web API already running on http://127.0.0.1:8000 with PID $existing_web_pid"
else
  nohup ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    < /dev/null >"$LOG_DIR/web.log" 2>&1 &
  echo $! >"$PID_DIR/web.pid"
  sleep 2
  web_runtime_pid="$(pgrep -f '/Users/tony/Projects/codex-workspace/manager_os_mvp/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000' | head -n 1 || true)"
  if [ -n "$web_runtime_pid" ] && kill -0 "$web_runtime_pid" 2>/dev/null; then
    echo "$web_runtime_pid" >"$PID_DIR/web.pid"
    echo "Started Web API on http://127.0.0.1:8000 with PID $web_runtime_pid"
  else
    echo "Web API failed to stay running. Check $LOG_DIR/web.log"
    rm -f "$PID_DIR/web.pid"
  fi
fi

if [ -n "$existing_bot_pid" ] && kill -0 "$existing_bot_pid" 2>/dev/null; then
  echo "$existing_bot_pid" >"$PID_DIR/telegram.pid"
  echo "Telegram bot already running with PID $existing_bot_pid"
else
  nohup ./.venv/bin/python -m app.telegram_bot \
    < /dev/null >"$LOG_DIR/telegram.log" 2>&1 &
  echo $! >"$PID_DIR/telegram.pid"
  sleep 2
  telegram_runtime_pid="$(pgrep -f '/Users/tony/Projects/codex-workspace/manager_os_mvp/.venv/bin/python -m app.telegram_bot' | head -n 1 || true)"
  if [ -n "$telegram_runtime_pid" ] && kill -0 "$telegram_runtime_pid" 2>/dev/null; then
    echo "$telegram_runtime_pid" >"$PID_DIR/telegram.pid"
    echo "Started Telegram bot with PID $telegram_runtime_pid"
  else
    echo "Telegram bot failed to stay running. Check $LOG_DIR/telegram.log"
    rm -f "$PID_DIR/telegram.pid"
  fi
fi

echo
echo "Logs:"
echo "  tail -f $LOG_DIR/web.log"
echo "  tail -f $LOG_DIR/telegram.log"
