# Next Steps

## Recommended Priority Order

### 1. Deadline UX

- add inline buttons under commitments: `Done`, `Move`
- add quick actions for overdue commitments
- show deadline state more clearly inside Telegram

### 2. Stronger Behavioral Pressure

- score days as `with management / without management`
- count skipped resets in a row
- escalate tone automatically after repeated drift
- include deadline discipline in weekly review

### 3. Better Commitment Model

- add owner field
- add contour field
- add business impact field
- separate personal task from delegated commitment

### 4. Review Layer

- weekly review should include:
  - broken commitments
  - moved commitments
  - fake deadlines
  - tasks that should not belong to the manager

### 5. Infrastructure

- move from SQLite to PostgreSQL
- expose web UI through nginx
- add auth for web access
- add backups for DB

### 6. Product Memory

- maintain this file after every major milestone
- maintain `PROJECT_STATE.md`
- write migration notes when schema changes

## If Starting A New Chat

Paste this summary:

`We are working on manager_os_mvp. Read README.md, PROJECT_STATE.md, and NEXT_STEPS.md first. The live runtime is on an Ubuntu VPS with systemd services manager-os-web and manager-os-bot. Telegram bot is the main interface. Continue from the documented state instead of redesigning from scratch.`
