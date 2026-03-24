"""Telegram bot application bootstrap."""

from __future__ import annotations

import asyncio
import logging
from datetime import date

from telegram import BotCommand, BotCommandScopeChat
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from torretray_bot.api_client import TorreTrayBackendClient
from torretray_bot.config import load_settings
from torretray_bot.handlers import (
    callback_query_handler,
    cancel_command,
    clear_preferences_command,
    current_preferences_command,
    language_command,
    meal_schedule_command,
    set_meal_schedule_command,
    set_preferences_command,
    start_command,
    text_message_handler,
    unregister_command,
)
from torretray_bot.localization import MESSAGES

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure human-readable console logging for local bot runs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def build_application(
    *,
    test_date_override: date | None = None,
) -> tuple[Application, TorreTrayBackendClient]:
    """Build the Telegram application and shared backend client."""
    settings = load_settings(test_date_override=test_date_override)
    backend_client = TorreTrayBackendClient(
        base_url=settings.backend_base_url,
        timeout_seconds=settings.http_timeout_seconds,
        test_date=settings.test_date,
    )

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["api_client"] = backend_client
    application.bot_data["admin_telegram_ids"] = frozenset(settings.admin_telegram_ids)
    application.bot_data["test_date"] = settings.test_date

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("set_preferences", set_preferences_command))
    application.add_handler(CommandHandler("mypreferences", current_preferences_command))
    application.add_handler(CommandHandler("clearpreferences", clear_preferences_command))
    application.add_handler(CommandHandler("language", language_command))
    application.add_handler(CommandHandler("unregister", unregister_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("mealschedule", meal_schedule_command))
    application.add_handler(CommandHandler("setmealschedule", set_meal_schedule_command))
    application.add_handler(
        CallbackQueryHandler(
            callback_query_handler,
            pattern=r"^(meal|view|lang|pick|any|skip|confirm|unregister|clearmeal|clearconfirm|schedweekday|schedservice):|^schedcancel$",
        )
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler)
    )
    return application, backend_client


async def _post_init(application: Application) -> None:
    """Register the Telegram command menu when the bot starts."""
    base_commands_en = [
        BotCommand("start", MESSAGES["en"]["cmd_start"]),
        BotCommand("set_preferences", MESSAGES["en"]["cmd_set_preferences"]),
        BotCommand("mypreferences", MESSAGES["en"]["cmd_mypreferences"]),
        BotCommand("clearpreferences", MESSAGES["en"]["cmd_clearpreferences"]),
        BotCommand("language", MESSAGES["en"]["cmd_language"]),
        BotCommand("unregister", MESSAGES["en"]["cmd_unregister"]),
        BotCommand("cancel", MESSAGES["en"]["cmd_cancel"]),
    ]
    base_commands_it = [
        BotCommand("start", MESSAGES["it"]["cmd_start"]),
        BotCommand("set_preferences", MESSAGES["it"]["cmd_set_preferences"]),
        BotCommand("mypreferences", MESSAGES["it"]["cmd_mypreferences"]),
        BotCommand("clearpreferences", MESSAGES["it"]["cmd_clearpreferences"]),
        BotCommand("language", MESSAGES["it"]["cmd_language"]),
        BotCommand("unregister", MESSAGES["it"]["cmd_unregister"]),
        BotCommand("cancel", MESSAGES["it"]["cmd_cancel"]),
    ]
    await application.bot.set_my_commands(
        base_commands_en
    )
    await application.bot.set_my_commands(
        base_commands_it,
        language_code="it",
    )

    admin_ids = application.bot_data.get("admin_telegram_ids", frozenset())
    admin_commands_en = base_commands_en + [
        BotCommand("mealschedule", MESSAGES["en"]["cmd_mealschedule"]),
        BotCommand("setmealschedule", MESSAGES["en"]["cmd_setmealschedule"]),
    ]
    admin_commands_it = base_commands_it + [
        BotCommand("mealschedule", MESSAGES["it"]["cmd_mealschedule"]),
        BotCommand("setmealschedule", MESSAGES["it"]["cmd_setmealschedule"]),
    ]
    for admin_id in admin_ids:
        scope = BotCommandScopeChat(chat_id=admin_id)
        await application.bot.set_my_commands(admin_commands_en, scope=scope)
        await application.bot.set_my_commands(
            admin_commands_it,
            scope=scope,
            language_code="it",
        )
    LOGGER.info("Telegram command menu registered.")


async def _post_shutdown(application: Application) -> None:
    """Close shared async resources when the bot stops."""
    backend_client = application.bot_data.get("api_client")
    if isinstance(backend_client, TorreTrayBackendClient):
        await backend_client.aclose()
        LOGGER.info("Backend API client closed.")


def main(*, test_date_override: date | None = None) -> None:
    """Run the Telegram bot in polling mode."""
    configure_logging()
    application, _ = build_application(test_date_override=test_date_override)
    application.post_init = _post_init
    application.post_shutdown = _post_shutdown

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        LOGGER.info("Starting TorreTray bot polling.")
        application.run_polling()
    finally:
        asyncio.set_event_loop(None)
        loop.close()
        LOGGER.info("TorreTray bot stopped.")
