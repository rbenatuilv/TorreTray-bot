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

Meal deadlines are controlled by the backend env, not by bot code. In `TorreTray-backend/.env` you can set:

- `MEAL_PREFERENCE_LUNCH_CUTOFF=10:00`
- `MEAL_PREFERENCE_DINNER_CUTOFF=16:00`

## Run

```bash
pip install -r requirements.txt
python -m torretray_bot
```
