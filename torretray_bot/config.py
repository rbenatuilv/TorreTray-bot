"""Environment-backed configuration for the Telegram bot."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration required by the bot."""

    telegram_bot_token: str
    backend_base_url: str
    http_timeout_seconds: float


def load_settings() -> Settings:
    """Load settings from environment variables and validate required values."""
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    backend_base_url = os.getenv("TORRETRAY_BACKEND_URL", "").strip()

    if not telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    if not backend_base_url:
        raise RuntimeError("TORRETRAY_BACKEND_URL is required.")

    return Settings(
        telegram_bot_token=telegram_bot_token,
        backend_base_url=backend_base_url.rstrip("/"),
        http_timeout_seconds=float(
            os.getenv("TORRETRAY_HTTP_TIMEOUT_SECONDS", "15")
        ),
    )
