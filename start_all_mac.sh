#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

osascript <<EOF
tell application "Terminal"
    activate
    do script "cd \"$PROJECT_DIR\" && ./run_local.sh"
    delay 1
    do script "cd \"$PROJECT_DIR\" && ./run_telegram_bot.sh" in front window
end tell
EOF

echo "Opened Terminal tabs for Web API and Telegram bot."
