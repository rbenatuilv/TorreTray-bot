# TorreTray Bot

Telegram bot for the TorreTray meal-preference flow. It talks to
`TorreTray-backend` for user registration, meal menus, preference validation,
language updates, and admin meal-schedule management.

## Main features

- links a Telegram account to an existing backend user by asking for the user's
  full name in surname-name order
- lets registered users configure lunch or dinner preferences with guided
  section-by-section buttons
- lets users review saved preferences, clear them, switch language, and unlink
  their Telegram account
- blocks the flow when the menu is unavailable, the reservation is missing, the
  cutoff time has passed, or the ticket is already printed
- sends the final confirmed preferences to `TorreTray-backend`
- exposes admin-only commands to inspect and update backend meal schedules

## User commands

- `/start`
- `/set_preferences`
- `/mypreferences`
- `/clearpreferences`
- `/language`
- `/unregister`
- `/cancel`

## Admin commands

Admins are identified through `TORRETRAY_ADMIN_TELEGRAM_IDS`.

- `/mealschedule`
- `/mealschedule monday`
- `/setmealschedule monday lunch 13:00 14:30`

`/setmealschedule` also supports the guided interactive flow with inline
buttons and typed times.

## Configuration

Create a `.env` from `.env.example` and set:

- `TELEGRAM_BOT_TOKEN`
- `TORRETRAY_BACKEND_URL`
- `TORRETRAY_HTTP_TIMEOUT_SECONDS` (optional)
- `TORRETRAY_ADMIN_TELEGRAM_IDS` as a comma-separated list of Telegram user ids

## Run locally

Install dependencies with either the package metadata or the pinned
requirements file:

```bash
pip install -e .
```

or

```bash
pip install -r requirements.txt
```

Then start the bot:

```bash
python -m torretray_bot
```

To force a specific effective date for backend requests without changing the
system clock:

```bash
python -m torretray_bot --test-time 2026-03-23
```

## How it fits with the other apps

- registration and preferred language are stored in the backend user record
- meal availability, menus, cutoffs, and saved preferences all come from the backend
- admin schedule commands update the same meal schedule used by the Raspberry Pi tray app

## Dev notes

- The bot registers localized Telegram command menus on startup, including
  admin-only commands for the configured admin ids.
- The meal preference flow is button-driven after registration; free text is
  mainly used for initial name registration and schedule time input in the
  guided admin flow.
- The bot supports English and Italian and will infer a default language from
  the Telegram profile before a user explicitly changes it.
