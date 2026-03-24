"""Environment-backed configuration for the Telegram bot."""

from __future__ import annotations

import os
from datetime import date
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration required by the bot."""

    telegram_bot_token: str
    backend_base_url: str
    http_timeout_seconds: float
    test_date: date | None
    admin_telegram_ids: tuple[int, ...]


def _parse_admin_ids(raw_value: str) -> tuple[int, ...]:
    values: list[int] = []
    for raw_item in raw_value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        values.append(int(item))
    return tuple(values)


def load_settings(*, test_date_override: date | None = None) -> Settings:
    """Load settings from environment variables and validate required values."""
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    backend_base_url = os.getenv("TORRETRAY_BACKEND_URL", "").strip()

    if not telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    if not backend_base_url:
        raise RuntimeError("TORRETRAY_BACKEND_URL is required.")

    test_date = test_date_override

    return Settings(
        telegram_bot_token=telegram_bot_token,
        backend_base_url=backend_base_url.rstrip("/"),
        http_timeout_seconds=float(
            os.getenv("TORRETRAY_HTTP_TIMEOUT_SECONDS", "15")
        ),
        test_date=test_date,
        admin_telegram_ids=_parse_admin_ids(
            os.getenv("TORRETRAY_ADMIN_TELEGRAM_IDS", "")
        ),
    )
