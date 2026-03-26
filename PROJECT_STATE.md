# Project State

## Purpose

Manager OS MVP is a behavioral correction system for a manager who wants to stop defaulting to executor mode.

## What Is Already Implemented

### Core

- FastAPI backend
- SQLite persistence
- local web UI
- OpenAI-backed analysis with fallback to local heuristics

### Telegram

- Telegram bot is the main interface
- normal text messages are treated as new entries
- slash commands are supported
- persistent menu button is supported
- inline menu actions are supported

### Rituals

- morning `daily reset`
- evening reminder
- weekly review
- scheduled push delivery
- day review persistence
- strictness mode escalation

### Role / Pattern Logic

- contour detection: `operational`, `managerial`, `architectural`
- role verdict: `executor`, `manager`, `mixed`
- pattern detection: rescue, hypercontrol, delegation avoidance, urgency, boundary failure
- repeat intervention when patterns recur

### Commitments / Deadlines

- step-by-step commitment creation
- exact deadline required: `YYYY-MM-DD HH:MM`
- `definition of done` required
- quality feedback on wording and deadline clarity
- commitment listing
- mark done
- move deadline
- due-soon reminders
- overdue reminders

### Discipline Engine

- day status classification
- automatic strictness mode:
  - `support`
  - `direct`
  - `hard`
- daily review persistence in `day_reviews`
- weekly review now includes commitment-discipline signals

### Deployment

- deployed to Ubuntu VPS
- bot runs as `manager-os-bot`
- web app runs as `manager-os-web`
- services restart automatically via `systemd`

## What Is Not Implemented Yet

- dashboard for analytics
- richer management score per day/week
- owner tracking for delegated work
- commitment scoring in weekly review
- public secured web access via nginx/domain
- PostgreSQL migration
- richer audit trail for every intervention

## Operational Truth

- Telegram bot is the real day-to-day interface
- web UI is auxiliary
- VPS is the source of truth runtime
- SQLite DB on VPS is the live state

## Important Files

- `app/main.py` — API and web
- `app/telegram_bot.py` — Telegram runtime
- `app/services.py` — behavioral logic and commitment logic
- `app/db.py` — schema bootstrap and DB helpers
- `app/llm_service.py` — OpenAI integration
- `.env.example` — environment template

## Important Runtime Locations

- App path on VPS: `/opt/manager_os_mvp`
- DB path on VPS: `/opt/manager_os_mvp/data/manager_os.db`
- Bot service: `manager-os-bot`
- Web service: `manager-os-web`
