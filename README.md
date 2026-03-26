# Manager OS MVP

Manager OS MVP is a behavioral support system for a manager. It is not a task manager and not a generic AI assistant. The system is designed to:

- catch drift from manager mode into executor mode
- enforce rituals: `daily reset`, evening check, weekly review
- track commitments and deadlines
- remember repeating rescue/control patterns
- work continuously through a Telegram bot deployed on a VPS

This repository is the project memory. If a future chat starts without previous context, begin with:

1. this `README.md`
2. [PROJECT_STATE.md](./PROJECT_STATE.md)
3. [NEXT_STEPS.md](./NEXT_STEPS.md)

## Current Architecture

- `FastAPI` app for API and local web UI
- `SQLite` for persistence
- `Telegram bot` as the main operational interface
- `OpenAI Responses API` as the optional LLM layer with fallback to local rules
- `systemd` deployment on Ubuntu VPS for 24/7 operation

## Current Capabilities

- capture of free-form entries from Telegram or web
- role/contour analysis with LLM fallback behavior
- daily reset ritual
- weekly review
- repeating-pattern detection and intervention
- commitments with strict deadlines and `definition of done`
- deadline reminders and overdue reminders
- push rituals by schedule
- Telegram menu and inline menu actions

## Быстрый старт

```bash
cd manager_os_mvp
./run_local.sh
```

После запуска открой `http://127.0.0.1:8000`.

Альтернатива вручную:

```bash
cd manager_os_mvp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Запуск всего сразу

Если хочешь запускать все одной командой:

```bash
cd manager_os_mvp
./start_all.sh
```

На Mac удобнее и надежнее открыть оба процесса в отдельных вкладках Terminal:

```bash
cd manager_os_mvp
./start_all_mac.sh
```

Проверить статус:

```bash
./status_all.sh
```

Остановить все:

```bash
./stop_all.sh
```

## Почему так

Это не финальная архитектура, а самый короткий путь проверить:

1. полезно ли тебе каждый день фиксировать ролевой сдвиг
2. цепляет ли тебя `daily reset`
3. видны ли повторяющиеся паттерны за несколько дней

## LLM-режим

Если хочешь включить OpenAI-анализ локально:

```bash
cd manager_os_mvp
cp .env.example .env
# потом заполни OPENAI_API_KEY в .env
./run_local.sh
```

Если ключа нет, приложение продолжит работать на встроенной rule-based логике.

## Telegram bot

Добавь токен в `.env`:

```bash
TELEGRAM_BOT_TOKEN=your_bot_token
```

Запуск:

```bash
cd manager_os_mvp
./run_telegram_bot.sh
```

Команды в Telegram:

- `/start` или `/help`
- `/menu`
- `/status`
- `/reset`
- `/commit`
- `/commitments`
- `/done ID`
- `/move ID`
- `/patterns`
- `/weekly`
- `/pause`
- `/resume`

Любое обычное сообщение бот трактует как новую запись, прогоняет через анализ и отвечает вердиктом.

Также в боте есть:

- постоянная кнопка `Меню`
- inline-меню для быстрых действий без ручного ввода команд
- inline-кнопки `Done` и `Move` под обязательствами

## Дедлайны и обязательства

`/commit` запускает пошаговую фиксацию обязательства:

1. конкретный результат
2. точный дедлайн в формате `YYYY-MM-DD HH:MM`
3. `definition of done`

Бот:

- не принимает размытые сроки вроде `к пятнице` или `до вечера`
- комментирует качество формулировки
- показывает список обязательств через `/commitments`
- позволяет отметить выполнение через `/done ID`
- позволяет перенести срок через `/move ID`
- сам напоминает о сроках, когда дедлайн близко или уже сорван
- показывает быстрые кнопки `Done` и `Move` прямо под открытыми обязательствами

## Push-ритуалы

Бот сам пишет по расписанию:

- утренний `daily reset`
- вечерний check
- недельная ревизия

Также бот умеет показывать статус дня:

- `День с управлением`
- `День под риском`
- `День без управления`

Команда:

```bash
/day
```

Настройка идет через `.env`:

```bash
TELEGRAM_TIMEZONE=Europe/Moscow
MORNING_RESET_TIME=09:00
EVENING_REVIEW_TIME=18:30
WEEKLY_REVIEW_DAY=6
WEEKLY_REVIEW_TIME=19:00
```

`WEEKLY_REVIEW_DAY` использует нумерацию Python weekday: `0=понедельник`, `6=воскресенье`.

## VPS Deployment

Production-like runtime is deployed on Ubuntu VPS and runs independently from the MacBook.

Services:

- `manager-os-web`
- `manager-os-bot`

Useful commands on the VPS:

```bash
systemctl status manager-os-web
systemctl status manager-os-bot
systemctl restart manager-os-web
systemctl restart manager-os-bot
journalctl -u manager-os-bot -f
journalctl -u manager-os-web -f
```

Current deployment keeps the web app bound to `127.0.0.1:8000` for safety. Telegram bot is the main public interface.

## Repo Workflow

This workspace currently has no Git remote configured. The recommended next step is:

1. create a dedicated GitHub repository for `manager_os_mvp`
2. add it as `origin`
3. commit the project docs and source
4. keep `PROJECT_STATE.md` and `NEXT_STEPS.md` updated after major milestones

Minimal sequence:

```bash
cd /Users/tony/Projects/codex-workspace
git init
git add manager_os_mvp
git commit -m "Initial Manager OS MVP"
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```
