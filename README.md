# TorreTray-bot

Telegram bot for the TorreTray meal-preference flow.

## Features

- Links a Telegram account to an existing backend user by asking for the user's full name.
- Lets registered users choose preferences for today's lunch or dinner.
- Stops the flow when the menu is unavailable, the reservation is missing, the ticket is already printed, or the cutoff time has passed.
- Sends the final confirmed preferences to `TorreTray-backend`.

## Configuration

Create a `.env` file from `.env.example` and set:

- `TELEGRAM_BOT_TOKEN`
- `TORRETRAY_BACKEND_URL`
- `TORRETRAY_HTTP_TIMEOUT_SECONDS` (optional)
- `TORRETRAY_ADMIN_TELEGRAM_IDS` with a comma-separated list of Telegram user ids allowed to manage schedules

Meal deadlines now come from the backend meal schedule. Admins can inspect or update one day's windows from Telegram:

- `/mealschedule`
- `/mealschedule monday`
- `/setmealschedule monday lunch 13:00 14:30`

## Run

```bash
pip install -r requirements.txt
python -m torretray_bot
```

To test against a specific date without changing `.env`:

```bash
python -m torretray_bot --test-time 2026-03-23
```
