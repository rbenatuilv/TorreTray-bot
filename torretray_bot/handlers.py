"""Telegram handlers for the TorreTray preference flow."""

from __future__ import annotations

import logging
from datetime import time

from telegram import CallbackQuery, Message, Update
from telegram.ext import ContextTypes

from torretray_bot.api_client import BackendApiError, TorreTrayBackendClient
from torretray_bot.keyboards import (
    clear_confirmation_keyboard,
    clear_preferences_keyboard,
    confirmation_keyboard,
    language_keyboard,
    meal_type_keyboard,
    schedule_service_keyboard,
    schedule_weekday_keyboard,
    section_keyboard,
    unregister_keyboard,
    view_preferences_keyboard,
)
from torretray_bot.localization import infer_language, normalize_language, t
from torretray_bot.models import (
    BackendUser,
    CurrentPreferences,
    MenuSection,
    PreferenceSession,
    ScheduleEditSession,
    WeekdayMealSchedule,
)

REGISTRATION_PENDING_KEY = "registration_pending"
PREFERENCE_SESSION_KEY = "preference_session"
REGISTERED_USER_KEY = "registered_user"
SCHEDULE_EDIT_SESSION_KEY = "schedule_edit_session"
LOGGER = logging.getLogger(__name__)
VALID_SERVICE_KEYS = {"breakfast", "lunch", "dinner"}
VALID_WEEKDAY_KEYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show a welcome message and explain the available commands."""
    LOGGER.info("Received /start from telegram user %s.", _telegram_id(update))
    message = update.effective_message
    telegram_user = update.effective_user
    if message is None or telegram_user is None:
        return

    user = await _fetch_registered_user(
        message=message,
        context=context,
        telegram_id=telegram_user.id,
    )
    if user is None:
        language = _language_for_update(update, context)
        context.user_data[REGISTRATION_PENDING_KEY] = True
        context.user_data.pop(PREFERENCE_SESSION_KEY, None)
        context.user_data.pop(REGISTERED_USER_KEY, None)
        await message.reply_text("👋 " + t(language, "start_unregistered"))
        return

    context.user_data.pop(REGISTRATION_PENDING_KEY, None)
    context.user_data[REGISTERED_USER_KEY] = user
    await message.reply_text(
        "👋 " + t(user.preferred_language, "start_registered", name=user.name)
    )


async def set_preferences_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Start the meal-preference flow for a registered user."""
    LOGGER.info(
        "Received /set_preferences from telegram user %s.",
        _telegram_id(update),
    )
    user = await _ensure_registered_user(
        message=update.effective_message,
        context=context,
        telegram_id=update.effective_user.id if update.effective_user else None,
    )
    if user is None:
        return
    await _show_meal_picker(
        update.effective_message,
        user,
        t(user.preferred_language, "config_meal_prompt"),
    )


async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Clear any in-progress registration or preference session."""
    LOGGER.info("Received /cancel from telegram user %s.", _telegram_id(update))
    _clear_transient_state(context)
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            t(_language_for_update(update, context), "cancelled")
        )


async def current_preferences_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show the meal picker used to inspect already saved preferences."""
    LOGGER.info(
        "Received /mypreferences from telegram user %s.",
        _telegram_id(update),
    )
    user = await _ensure_registered_user(
        message=update.effective_message,
        context=context,
        telegram_id=update.effective_user.id if update.effective_user else None,
    )
    if user is None:
        return
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            "👀 "
            + t(
                user.preferred_language,
                "view_preferences_prompt",
                name=user.name,
            ),
            reply_markup=view_preferences_keyboard(user.preferred_language),
        )


async def clear_preferences_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show the meal picker used to clear already saved preferences."""
    LOGGER.info(
        "Received /clearpreferences from telegram user %s.",
        _telegram_id(update),
    )
    user = await _ensure_registered_user(
        message=update.effective_message,
        context=context,
        telegram_id=update.effective_user.id if update.effective_user else None,
    )
    if user is None:
        return
    if update.effective_message is not None:
        await update.effective_message.reply_text(
            "🗑️ "
            + t(
                user.preferred_language,
                "clear_preferences_prompt",
                name=user.name,
            ),
            reply_markup=clear_preferences_keyboard(user.preferred_language),
        )


async def language_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show the language selector and let the user pick English or Italian."""
    LOGGER.info("Received /language from telegram user %s.", _telegram_id(update))
    if update.effective_message is None:
        return
    await update.effective_message.reply_text(
        t(_language_for_update(update, context), "language_prompt"),
        reply_markup=language_keyboard(),
    )


async def meal_schedule_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show one day's backend-defined meal schedule to admins."""
    message = update.effective_message
    if not await _ensure_admin_access(update, context):
        return
    if message is None:
        return

    language = _language_for_update(update, context)
    try:
        if context.args:
            weekday = _parse_weekday_arg(context.args[0])
            if weekday is None:
                await message.reply_text(t(language, "schedule_invalid_weekday"))
                await message.reply_text(t(language, "meal_schedule_usage"))
                return
            schedule = await get_api_client(context).get_meal_schedule_template(
                weekday=weekday
            )
            await message.reply_text(_format_weekday_schedule(language, schedule))
            return

        schedules = await get_api_client(context).list_meal_schedule_templates()
    except BackendApiError as exc:
        LOGGER.warning("Could not load meal schedule templates: %s", exc.message)
        await message.reply_text(exc.message)
        return

    await message.reply_text(_format_weekly_schedules(language, schedules))


async def set_meal_schedule_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Start the guided admin flow used to update a meal schedule window."""
    message = update.effective_message
    if not await _ensure_admin_access(update, context):
        return
    if message is None:
        return

    language = _language_for_update(update, context)
    if len(context.args) == 4:
        await _update_schedule_from_args(message, context, language)
        return

    if context.args:
        await message.reply_text(t(language, "set_meal_schedule_usage"))
        return

    context.user_data[SCHEDULE_EDIT_SESSION_KEY] = ScheduleEditSession()
    await message.reply_text(
        t(language, "schedule_pick_weekday"),
        reply_markup=schedule_weekday_keyboard(language),
    )


async def unregister_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Ask the user to confirm Telegram unlinking."""
    LOGGER.info("Received /unregister from telegram user %s.", _telegram_id(update))
    user = await _ensure_registered_user(
        message=update.effective_message,
        context=context,
        telegram_id=update.effective_user.id if update.effective_user else None,
    )
    if user is None:
        if update.effective_message is not None:
            await update.effective_message.reply_text(
                t(_language_for_update(update, context), "unregister_requires_registration")
            )
        return

    if update.effective_message is not None:
        await update.effective_message.reply_text(
            t(user.preferred_language, "unregister_prompt"),
            reply_markup=unregister_keyboard(user.preferred_language),
        )


async def text_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle registration-name input and generic free text."""
    message = update.effective_message
    if message is None or message.text is None:
        return

    if context.user_data.get(REGISTRATION_PENDING_KEY):
        LOGGER.info(
            "Registration name received from telegram user %s: %s",
            message.from_user.id if message.from_user else "unknown",
            message.text.strip(),
        )
        await _register_current_user(message, context, message.text.strip())
        return

    if await _handle_schedule_edit_text(message, context):
        return

    await message.reply_text(
        t(_language_for_message(message, context), "plain_help")
    )


async def callback_query_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle all inline-button interactions."""
    query = update.callback_query
    if query is None or query.data is None or query.message is None:
        return

    await query.answer()
    LOGGER.info(
        "Callback received from telegram user %s: %s",
        query.from_user.id if query.from_user else "unknown",
        query.data,
    )

    if query.data.startswith("meal:"):
        meal_type = query.data.split(":", maxsplit=1)[1]
        await _start_preference_flow(query, context, meal_type)
        return

    if query.data.startswith("lang:"):
        language = query.data.split(":", maxsplit=1)[1]
        await _update_language(query, context, language)
        return

    if query.data == "schedcancel":
        context.user_data.pop(SCHEDULE_EDIT_SESSION_KEY, None)
        await query.edit_message_text(
            t(_language_for_query(query, context), "schedule_cancelled")
        )
        return

    if query.data.startswith("schedweekday:"):
        weekday = query.data.split(":", maxsplit=1)[1]
        await _handle_schedule_weekday_choice(query, context, weekday)
        return

    if query.data.startswith("schedservice:"):
        service_key = query.data.split(":", maxsplit=1)[1]
        await _handle_schedule_service_choice(query, context, service_key)
        return

    if query.data == "unregister:yes":
        await _unregister_current_user(query, context)
        return

    if query.data == "unregister:no":
        await query.message.reply_text(
            t(_language_for_query(query, context), "cancelled")
        )
        return

    if query.data.startswith("view:"):
        meal_type = query.data.split(":", maxsplit=1)[1]
        await _show_current_preferences(query, context, meal_type)
        return

    if query.data.startswith("clearmeal:"):
        meal_type = query.data.split(":", maxsplit=1)[1]
        await _prompt_clear_preferences(query, context, meal_type)
        return

    if query.data.startswith("clearconfirm:"):
        _, meal_type, action = query.data.split(":")
        if action == "yes":
            await _clear_current_preferences(query, context, meal_type)
        else:
            await query.edit_message_text(
                "↩️ " + t(_language_for_query(query, context), "clear_preferences_cancelled")
            )
        return

    if query.data.startswith("pick:"):
        _, raw_section_index, raw_option_index = query.data.split(":")
        await _record_section_choice(
            query,
            context,
            section_index=int(raw_section_index),
            option_index=int(raw_option_index),
            selected=True,
            no_specific_preference=False,
        )
        return

    if query.data.startswith("any:"):
        _, raw_section_index = query.data.split(":")
        await _record_section_choice(
            query,
            context,
            section_index=int(raw_section_index),
            option_index=None,
            selected=True,
            no_specific_preference=True,
        )
        return

    if query.data.startswith("skip:"):
        _, raw_section_index = query.data.split(":")
        await _record_section_choice(
            query,
            context,
            section_index=int(raw_section_index),
            option_index=None,
            selected=False,
            no_specific_preference=False,
        )
        return

    if query.data == "confirm:yes":
        await _submit_preferences(query, context)
        return

    if query.data == "confirm:no":
        context.user_data.pop(PREFERENCE_SESSION_KEY, None)
        await query.edit_message_text(
            "↩️ " + t(_language_for_query(query, context), "nothing_saved"),
        )
        if query.message is not None:
            await query.message.reply_text(
                "✨ " + t(_language_for_query(query, context), "config_meal_prompt"),
                reply_markup=meal_type_keyboard(_language_for_query(query, context)),
            )


def get_api_client(context: ContextTypes.DEFAULT_TYPE) -> TorreTrayBackendClient:
    """Return the shared backend API client stored on the application."""
    return context.application.bot_data["api_client"]


async def _ensure_registered_user(
    *,
    message: Message | None,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int | None,
) -> BackendUser | None:
    """Return the registered backend user or prompt for registration."""
    if message is None or telegram_id is None:
        return None

    user = await _fetch_registered_user(
        message=message,
        context=context,
        telegram_id=telegram_id,
    )
    if user is None:
        LOGGER.info("Telegram user %s is not registered yet.", telegram_id)
        context.user_data[REGISTRATION_PENDING_KEY] = True
        context.user_data.pop(PREFERENCE_SESSION_KEY, None)
        context.user_data.pop(REGISTERED_USER_KEY, None)
        await message.reply_text(
            t(_language_for_message(message, context), "not_linked")
        )
        return None

    context.user_data.pop(REGISTRATION_PENDING_KEY, None)
    context.user_data[REGISTERED_USER_KEY] = user
    LOGGER.info(
        "Telegram user %s is linked to backend user %s (%s).",
        telegram_id,
        user.id,
        user.name,
    )
    return user


async def _fetch_registered_user(
    *,
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    telegram_id: int,
) -> BackendUser | None:
    """Look up the registered backend user without sending registration prompts."""
    try:
        user = await get_api_client(context).get_registered_user(str(telegram_id))
    except BackendApiError as exc:
        LOGGER.exception(
            "Backend lookup failed while checking registration for telegram user %s.",
            telegram_id,
        )
        await message.reply_text(exc.message)
        return None

    return user


async def _register_current_user(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    full_name: str,
) -> None:
    """Try to link the current Telegram account using the provided name."""
    if not full_name:
        await message.reply_text(t(_language_for_message(message, context), "send_full_name"))
        return

    telegram_user = message.from_user
    if telegram_user is None:
        await message.reply_text(
            t(_language_for_message(message, context), "cannot_determine_telegram")
        )
        return

    try:
        user = await get_api_client(context).register_telegram_user(
            name=full_name,
            telegram_id=str(telegram_user.id),
        )
    except BackendApiError as exc:
        LOGGER.warning(
            "Registration failed for telegram user %s: %s",
            telegram_user.id,
            exc.message,
        )
        await message.reply_text(
            t(
                _language_for_message(message, context),
                "registration_retry",
                detail=exc.message,
            )
        )
        return

    context.user_data.pop(REGISTRATION_PENDING_KEY, None)
    context.user_data[REGISTERED_USER_KEY] = user
    LOGGER.info(
        "Telegram user %s registered successfully as backend user %s (%s).",
        telegram_user.id,
        user.id,
        user.name,
    )
    await _show_meal_picker(
        message,
        user,
        "🎉 " + t(
            user.preferred_language,
            "registration_completed",
            name=user.name,
        ),
    )


async def _show_meal_picker(
    message: Message | None,
    user: BackendUser,
    prompt: str,
) -> None:
    """Send the lunch/dinner selection keyboard."""
    if message is None:
        return
    await message.reply_text(
        f"✨ {prompt}\n\n👤 {t(user.preferred_language, 'registered_user')}: {user.name}",
        reply_markup=meal_type_keyboard(user.preferred_language),
    )


async def _start_preference_flow(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    meal_type: str,
) -> None:
    """Fetch the backend context and start the section-by-section flow."""
    user = await _ensure_registered_user(
        message=query.message,
        context=context,
        telegram_id=query.from_user.id if query.from_user else None,
    )
    if user is None:
        return
    language = user.preferred_language

    try:
        preference_context = await get_api_client(context).get_preference_context(
            user_id=user.id,
            meal_type=meal_type,
        )
    except BackendApiError as exc:
        LOGGER.warning(
            "Could not load preference context for backend user %s and meal %s: %s",
            user.id,
            meal_type,
            exc.message,
        )
        await query.message.reply_text(exc.message)
        return

    if not preference_context.can_set_preferences:
        context.user_data.pop(PREFERENCE_SESSION_KEY, None)
        LOGGER.info(
            "Preference flow blocked for backend user %s and meal %s: %s",
            user.id,
            meal_type,
            preference_context.blocked_reason,
        )
        await query.message.reply_text(
            "⏳ " + (
                preference_context.blocked_message
                or t(language, "blocked_prefix", message="")
            ).strip()
        )
        return

    if preference_context.meal_status_id is None or not preference_context.sections:
        context.user_data.pop(PREFERENCE_SESSION_KEY, None)
        LOGGER.info(
            "No configurable sections found for backend user %s and meal %s.",
            user.id,
            meal_type,
        )
        await query.message.reply_text(
            "ℹ️ " + t(language, "no_sections")
        )
        return

    context.user_data[PREFERENCE_SESSION_KEY] = PreferenceSession(
        meal_status_id=preference_context.meal_status_id,
        meal_type=preference_context.meal_type,
        meal_date=preference_context.date,
        sections=preference_context.sections,
    )
    LOGGER.info(
        "Starting preference flow for backend user %s and meal %s with %s sections.",
        user.id,
        meal_type,
        len(preference_context.sections),
    )
    await query.message.reply_text(
        "🍽️ "
        + t(
            language,
            "setting_preferences_for",
            meal=_meal_label(language, meal_type),
        )
    )
    await _send_current_section_prompt(query.message, context)


async def _show_current_preferences(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    meal_type: str,
) -> None:
    """Fetch and show the currently saved preferences for one meal."""
    user = await _ensure_registered_user(
        message=query.message,
        context=context,
        telegram_id=query.from_user.id if query.from_user else None,
    )
    if user is None:
        return
    language = user.preferred_language

    try:
        current_preferences = await get_api_client(context).get_current_preferences(
            user_id=user.id,
            meal_type=meal_type,
        )
    except BackendApiError as exc:
        LOGGER.warning(
            "Could not load current preferences for backend user %s and meal %s: %s",
            user.id,
            meal_type,
            exc.message,
        )
        await query.message.reply_text(exc.message)
        return

    LOGGER.info(
        "Showing current preferences for backend user %s and meal %s.",
        user.id,
        meal_type,
    )
    await query.message.reply_text(
        _format_current_preferences(user.preferred_language, current_preferences)
    )


async def _prompt_clear_preferences(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    meal_type: str,
) -> None:
    """Show the confirmation prompt for clearing one meal's saved preferences."""
    user = await _ensure_registered_user(
        message=query.message,
        context=context,
        telegram_id=query.from_user.id if query.from_user else None,
    )
    if user is None:
        return

    try:
        current_preferences = await get_api_client(context).get_current_preferences(
            user_id=user.id,
            meal_type=meal_type,
        )
    except BackendApiError as exc:
        LOGGER.warning(
            "Could not load current preferences for clearing for backend user %s and meal %s: %s",
            user.id,
            meal_type,
            exc.message,
        )
        await query.message.reply_text(exc.message)
        return

    language = user.preferred_language
    meal_label = _meal_label(language, meal_type)
    if (
        not current_preferences.reservation_found
        or current_preferences.meal_status_id is None
        or current_preferences.preferences is None
    ):
        await query.edit_message_text(
            "ℹ️ " + t(language, "no_saved_preferences", meal=meal_label.lower())
        )
        return

    await query.edit_message_text(
        "🗑️ "
        + t(
            language,
            "clear_preferences_confirm",
            meal=meal_label,
            date=current_preferences.date,
        ),
        reply_markup=clear_confirmation_keyboard(language, meal_type),
    )


async def _clear_current_preferences(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    meal_type: str,
) -> None:
    """Clear one meal's saved preferences through the backend API."""
    user = await _ensure_registered_user(
        message=query.message,
        context=context,
        telegram_id=query.from_user.id if query.from_user else None,
    )
    if user is None:
        return

    try:
        current_preferences = await get_api_client(context).get_current_preferences(
            user_id=user.id,
            meal_type=meal_type,
        )
    except BackendApiError as exc:
        LOGGER.warning(
            "Could not reload current preferences before clearing for backend user %s and meal %s: %s",
            user.id,
            meal_type,
            exc.message,
        )
        await query.message.reply_text(exc.message)
        return

    if current_preferences.meal_status_id is None or current_preferences.preferences is None:
        await query.edit_message_text(
            "ℹ️ "
            + t(
                user.preferred_language,
                "no_saved_preferences",
                meal=_meal_label(user.preferred_language, meal_type).lower(),
            )
        )
        return

    try:
        await get_api_client(context).clear_preferences(
            meal_status_id=current_preferences.meal_status_id,
        )
    except BackendApiError as exc:
        LOGGER.warning(
            "Could not clear preferences for backend user %s and meal %s: %s",
            user.id,
            meal_type,
            exc.message,
        )
        await query.message.reply_text(exc.message)
        return

    LOGGER.info(
        "Cleared saved preferences for backend user %s and meal %s.",
        user.id,
        meal_type,
    )
    await query.edit_message_text(
        "🧹 "
        + t(
            user.preferred_language,
            "preferences_cleared",
            meal=_meal_label(user.preferred_language, meal_type).lower(),
        )
    )


async def _record_section_choice(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    section_index: int,
    option_index: int | None,
    selected: bool,
    no_specific_preference: bool,
) -> None:
    """Store one section answer and move the flow forward."""
    session = context.user_data.get(PREFERENCE_SESSION_KEY)
    if not isinstance(session, PreferenceSession) or query.message is None:
        await query.message.reply_text(
            "⚠️ " + t(_language_for_query(query, context), "no_active_flow")
        )
        return

    if section_index != session.current_index:
        await query.message.reply_text(
            "⚠️ " + t(_language_for_query(query, context), "step_not_active")
        )
        return

    section = session.sections[section_index]
    selected_dish = None
    selected_display_dish = None
    if selected:
        if no_specific_preference:
            selected_display_dish = t(
                _stored_language(context),
                "summary_no_preference",
            )
        elif option_index is None or option_index >= len(section.options):
            await query.message.reply_text(
                "⚠️ " + t(_language_for_query(query, context), "invalid_option")
            )
            return
        else:
            option = section.options[option_index]
            selected_dish = option.raw_dish
            selected_display_dish = option.dish

    selection = session.record_selection(
        section_index=section_index,
        selected=selected,
        selected_dish=selected_dish,
        no_specific_preference=no_specific_preference,
        selected_display_dish=selected_display_dish,
    )
    LOGGER.info(
        "Section answered for meal %s: %s -> %s",
        session.meal_type,
        section.name,
        (
            selection.display_selected_dish
            if selection.display_selected_dish is not None
            else "No"
        ),
    )
    await query.edit_message_text(
        _build_acknowledgement(
            _stored_language(context),
            section,
            selection.display_selected_dish,
            selection.no_specific_preference,
        )
    )

    if session.is_complete():
        await _send_confirmation_prompt(query.message, context, session)
        return

    await _send_current_section_prompt(query.message, context)


async def _send_current_section_prompt(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Send the next section prompt in the active preference flow."""
    session = context.user_data.get(PREFERENCE_SESSION_KEY)
    if not isinstance(session, PreferenceSession):
        return

    section = session.current_section()
    if section is None:
        await _send_confirmation_prompt(message, context, session)
        return

    await message.reply_text(
        _build_section_prompt(
            _stored_language(context),
            section,
            session.current_index,
            len(session.sections),
        ),
        reply_markup=section_keyboard(
            _stored_language(context),
            session.current_index,
            section,
        ),
    )


async def _send_confirmation_prompt(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    session: PreferenceSession,
) -> None:
    """Send the final summary and confirmation buttons."""
    language = _stored_language(context)
    summary_lines = "\n".join(session.build_summary_lines(language))
    await message.reply_text(
        t(
            language,
            "confirm_preferences",
            meal=_meal_label(language, session.meal_type),
            date=session.meal_date,
            summary=summary_lines,
        ),
        reply_markup=confirmation_keyboard(language),
    )


async def _submit_preferences(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Submit the collected preferences to the backend."""
    session = context.user_data.get(PREFERENCE_SESSION_KEY)
    if not isinstance(session, PreferenceSession) or query.message is None:
        await query.message.reply_text(
            "⚠️ " + t(_language_for_query(query, context), "no_active_flow")
        )
        return

    try:
        await get_api_client(context).update_preferences(
            meal_status_id=session.meal_status_id,
            payload=session.to_update_payload(),
        )
    except BackendApiError as exc:
        context.user_data.pop(PREFERENCE_SESSION_KEY, None)
        LOGGER.warning(
            "Preference submission failed for meal_status %s: %s",
            session.meal_status_id,
            exc.message,
        )
        await query.message.reply_text(exc.message)
        return

    context.user_data.pop(PREFERENCE_SESSION_KEY, None)
    LOGGER.info(
        "Preferences saved successfully for meal_status %s.",
        session.meal_status_id,
    )
    await query.edit_message_text(
        "🎉 "
        + t(
            _stored_language(context),
            "preferences_saved",
            summary="\n".join(session.build_summary_lines(_stored_language(context))),
        )
    )


def _build_section_prompt(
    language: str,
    section: MenuSection,
    section_index: int,
    total_sections: int,
) -> str:
    """Render the message shown for one menu section."""
    if len(section.options) == 1:
        option = section.options[0]
        option_text = option.dish
        if option.flags:
            option_text = f"{option_text} ({option.flags})"
        return (
            "🍴 "
            + t(
                language,
                "section_single_prompt",
                index=section_index + 1,
                total=total_sections,
                section=section.name,
                option=option_text,
            )
        )

    option_lines = []
    for option_number, option in enumerate(section.options, start=1):
        option_text = option.dish
        if option.flags:
            option_text = f"{option_text} ({option.flags})"
        option_lines.append(f"{option_number}. {option_text}")

    return "🍴 " + t(
        language,
        "section_multi_prompt",
        index=section_index + 1,
        total=total_sections,
        section=section.name,
        options="\n".join(option_lines),
    )


def _build_acknowledgement(
    language: str,
    section: MenuSection,
    selected_dish: str | None,
    no_specific_preference: bool = False,
) -> str:
    """Render the text shown after one section has been answered."""
    if selected_dish is None:
        if no_specific_preference:
            return f"🤷 {section.name}: {t(language, 'summary_no_preference')}"
        return (
            f"🚫 {section.name}: "
            f"{t(language, 'button_no')} {section.name}"
        )
    return f"✅ {section.name}: {selected_dish}"


def _format_current_preferences(
    language: str,
    current_preferences: CurrentPreferences,
) -> str:
    """Render the current saved preferences for one meal."""
    meal_label = _meal_label(language, current_preferences.meal_type)
    if not current_preferences.reservation_found:
        return (
            "ℹ️ "
            + t(
                language,
                "no_reservation_for_view",
                meal=meal_label.lower(),
            )
        )

    if current_preferences.preferences is None:
        return "ℹ️ " + t(
            language,
            "no_saved_preferences",
            meal=meal_label.lower(),
        )

    sections = current_preferences.preferences.get("sections")
    if not isinstance(sections, list) or not sections:
        return "ℹ️ " + t(
            language,
            "preferences_without_sections",
            meal=meal_label.lower(),
        )

    lines = [
        f"👀 {t(language, 'current_preferences_header', meal=meal_label, date=current_preferences.date)}",
        "",
    ]
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_name = str(section.get("section_name", t(language, "unknown")))
        selected = bool(section.get("selected"))
        selected_dish = section.get("selected_dish")
        no_specific_preference = bool(section.get("no_specific_preference"))
        if selected and selected_dish:
            lines.append(f"• {section_name}: {selected_dish}")
        elif selected and no_specific_preference:
            lines.append(f"• {section_name}: {t(language, 'summary_no_preference')}")
        else:
            lines.append(f"• {section_name}: {t(language, 'button_no')} {section_name}")

    if current_preferences.printed:
        lines.extend(["", f"🧾 {t(language, 'ticket_printed')}"])

    return "\n".join(lines)


def _clear_transient_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove transient user conversation state."""
    context.user_data.pop(REGISTRATION_PENDING_KEY, None)
    context.user_data.pop(PREFERENCE_SESSION_KEY, None)
    context.user_data.pop(SCHEDULE_EDIT_SESSION_KEY, None)


async def _update_schedule_from_args(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    language: str,
) -> None:
    """Keep supporting the direct four-argument schedule update form."""
    raw_weekday, raw_service_key, raw_start_time, raw_end_time = context.args
    weekday = _parse_weekday_arg(raw_weekday)
    service_key = raw_service_key.lower().strip()
    if weekday is None:
        await message.reply_text(t(language, "schedule_invalid_weekday"))
        return
    if service_key not in VALID_SERVICE_KEYS:
        await message.reply_text(t(language, "schedule_invalid_service"))
        return
    if _parse_schedule_time(raw_start_time) is None or _parse_schedule_time(raw_end_time) is None:
        await message.reply_text(t(language, "schedule_invalid_time"))
        return

    try:
        schedule = await get_api_client(context).update_meal_schedule_template_window(
            weekday=weekday,
            service_key=service_key,
            start_time=raw_start_time,
            end_time=raw_end_time,
        )
    except BackendApiError as exc:
        LOGGER.warning(
            "Could not update meal schedule for %s %s: %s",
            weekday,
            service_key,
            exc.message,
        )
        await message.reply_text(exc.message)
        return

    await message.reply_text(
        t(
            language,
            "schedule_updated",
            service=_service_label(language, service_key),
            weekday=_weekday_label(language, schedule.weekday, schedule.weekday_label),
            start_time=raw_start_time,
            end_time=raw_end_time,
        )
    )
    await message.reply_text(_format_weekday_schedule(language, schedule))


async def _handle_schedule_weekday_choice(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    weekday: str,
) -> None:
    """Store the chosen weekday and ask which service window to edit."""
    language = _language_for_query(query, context)
    session = context.user_data.get(SCHEDULE_EDIT_SESSION_KEY)
    if not isinstance(session, ScheduleEditSession):
        session = ScheduleEditSession()
        context.user_data[SCHEDULE_EDIT_SESSION_KEY] = session
    session.weekday = weekday
    session.service_key = None
    session.start_time = None
    session.awaiting_time_field = None

    await query.edit_message_text(
        t(
            language,
            "schedule_pick_service",
            weekday=_weekday_label(language, weekday, weekday.title()),
        ),
        reply_markup=schedule_service_keyboard(language),
    )


async def _handle_schedule_service_choice(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    service_key: str,
) -> None:
    """Store the chosen service and ask the admin for the start time."""
    language = _language_for_query(query, context)
    session = context.user_data.get(SCHEDULE_EDIT_SESSION_KEY)
    if not isinstance(session, ScheduleEditSession) or session.weekday is None:
        await query.edit_message_text(t(language, "schedule_no_active_edit"))
        return

    session.service_key = service_key
    session.start_time = None
    session.awaiting_time_field = "start_time"
    await query.edit_message_text(
        t(
            language,
            "schedule_prompt_start_time",
            service=_service_label(language, service_key),
            weekday=_weekday_label(language, session.weekday, session.weekday.title()),
        )
    )


async def _handle_schedule_edit_text(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Handle start/end time input for the active admin schedule flow."""
    session = context.user_data.get(SCHEDULE_EDIT_SESSION_KEY)
    if not isinstance(session, ScheduleEditSession):
        return False

    language = _language_for_message(message, context)
    raw_value = message.text.strip()
    parsed_time = _parse_schedule_time(raw_value)
    if parsed_time is None:
        await message.reply_text(t(language, "schedule_invalid_time"))
        return True

    if (
        session.awaiting_time_field == "start_time"
        and session.weekday is not None
        and session.service_key is not None
    ):
        session.start_time = parsed_time.strftime("%H:%M")
        session.awaiting_time_field = "end_time"
        await message.reply_text(
            t(language, "schedule_time_saved", time=session.start_time)
        )
        await message.reply_text(
            t(
                language,
                "schedule_prompt_end_time",
                service=_service_label(language, session.service_key),
                weekday=_weekday_label(language, session.weekday, session.weekday.title()),
            )
        )
        return True

    if (
        session.awaiting_time_field == "end_time"
        and session.weekday is not None
        and session.service_key is not None
        and session.start_time is not None
    ):
        try:
            schedule = await get_api_client(context).update_meal_schedule_template_window(
                weekday=session.weekday,
                service_key=session.service_key,
                start_time=session.start_time,
                end_time=parsed_time.strftime("%H:%M"),
            )
        except BackendApiError as exc:
            LOGGER.warning(
                "Could not update meal schedule for %s %s: %s",
                session.weekday,
                session.service_key,
                exc.message,
            )
            await message.reply_text(exc.message)
            return True

        context.user_data.pop(SCHEDULE_EDIT_SESSION_KEY, None)
        await message.reply_text(
            t(
                language,
                "schedule_updated",
                service=_service_label(language, session.service_key),
                weekday=_weekday_label(language, schedule.weekday, schedule.weekday_label),
                start_time=session.start_time,
                end_time=parsed_time.strftime("%H:%M"),
            )
        )
        await message.reply_text(_format_weekday_schedule(language, schedule))
        return True

    context.user_data.pop(SCHEDULE_EDIT_SESSION_KEY, None)
    await message.reply_text(t(language, "schedule_no_active_edit"))
    return True


async def _ensure_admin_access(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """Return whether the current Telegram user is allowed to run admin commands."""
    message = update.effective_message
    telegram_user = update.effective_user
    if message is None or telegram_user is None:
        return False
    admin_ids = context.application.bot_data.get("admin_telegram_ids", frozenset())
    if telegram_user.id in admin_ids:
        return True
    await message.reply_text(t(_language_for_update(update, context), "admin_only"))
    return False


def _telegram_id(update: Update) -> str:
    """Return a compact log-friendly Telegram user id."""
    if update.effective_user is None:
        return "unknown"
    return str(update.effective_user.id)


async def _update_language(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    language: str,
) -> None:
    """Persist the preferred language for the current user."""
    language = normalize_language(language)
    user = context.user_data.get(REGISTERED_USER_KEY)
    if not isinstance(user, BackendUser):
        await query.message.reply_text(t(language, "language_requires_registration"))
        return

    updated_user = await get_api_client(context).update_user_language(
        user_id=user.id,
        preferred_language=language,
    )
    context.user_data[REGISTERED_USER_KEY] = updated_user
    await query.message.reply_text(
        t(
            updated_user.preferred_language,
            "language_updated",
            language_name=t(
                updated_user.preferred_language,
                f"button_language_{'english' if language == 'en' else 'italian'}",
            ),
        )
    )


async def _unregister_current_user(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Unlink the current Telegram account from the backend user."""
    user = context.user_data.get(REGISTERED_USER_KEY)
    if not isinstance(user, BackendUser) or query.from_user is None:
        await query.message.reply_text(
            t(_language_for_query(query, context), "unregister_requires_registration")
        )
        return

    updated_user = await get_api_client(context).unregister_telegram_user(
        user_id=user.id,
        telegram_id=str(query.from_user.id),
    )
    LOGGER.info(
        "Telegram user %s unregistered backend user %s.",
        query.from_user.id,
        user.id,
    )
    context.user_data.pop(REGISTERED_USER_KEY, None)
    context.user_data.pop(PREFERENCE_SESSION_KEY, None)
    context.user_data[REGISTRATION_PENDING_KEY] = True
    await query.message.reply_text(
        t(updated_user.preferred_language, "unregister_done")
    )


def _language_for_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Return the active language for one update."""
    user = context.user_data.get(REGISTERED_USER_KEY)
    if isinstance(user, BackendUser):
        return normalize_language(user.preferred_language)
    if update.effective_user is not None:
        return infer_language(update.effective_user.language_code)
    return "en"


def _language_for_message(message: Message, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Return the active language for one message."""
    user = context.user_data.get(REGISTERED_USER_KEY)
    if isinstance(user, BackendUser):
        return normalize_language(user.preferred_language)
    if message.from_user is not None:
        return infer_language(message.from_user.language_code)
    return "en"


def _language_for_query(query: CallbackQuery, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Return the active language for one callback query."""
    user = context.user_data.get(REGISTERED_USER_KEY)
    if isinstance(user, BackendUser):
        return normalize_language(user.preferred_language)
    if query.from_user is not None:
        return infer_language(query.from_user.language_code)
    return "en"


def _stored_language(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Return the language stored for the currently registered user."""
    user = context.user_data.get(REGISTERED_USER_KEY)
    if isinstance(user, BackendUser):
        return normalize_language(user.preferred_language)
    return "en"


def _parse_weekday_arg(raw_value: str | None) -> str | None:
    """Parse one weekday template key."""
    if raw_value is None:
        return None
    weekday = raw_value.strip().lower()
    if weekday in VALID_WEEKDAY_KEYS:
        return weekday
    LOGGER.info("Invalid admin schedule weekday received: %s", raw_value)
    return None


def _parse_schedule_time(raw_value: str) -> time | None:
    """Parse one HH:MM time argument."""
    try:
        return time.fromisoformat(raw_value)
    except ValueError:
        return None


def _format_weekly_schedules(
    language: str,
    schedules: list[WeekdayMealSchedule],
) -> str:
    """Render the full monday-sunday schedule template list."""
    if not schedules:
        return t(language, "weekly_schedule_empty")
    lines = [t(language, "weekly_schedule_header"), ""]
    for index, schedule in enumerate(schedules):
        if index:
            lines.append("")
        lines.extend(_weekday_schedule_lines(language, schedule))
    return "\n".join(lines)


def _format_weekday_schedule(language: str, schedule: WeekdayMealSchedule) -> str:
    """Render one weekday schedule template."""
    return "\n".join(_weekday_schedule_lines(language, schedule))


def _weekday_schedule_lines(
    language: str,
    schedule: WeekdayMealSchedule,
) -> list[str]:
    """Build the message lines for one weekday schedule template."""
    lines = [
        t(
            language,
            "schedule_header",
            weekday=_weekday_label(language, schedule.weekday, schedule.weekday_label),
        ),
        "",
    ]
    for window in schedule.windows:
        lines.append(
            t(
                language,
                "schedule_window_line",
                service=_service_label(language, window.service_key),
                start_time=window.start_time,
                end_time=window.end_time,
            )
        )
        if window.preference_cutoff_time is not None:
            lines.append(
                t(
                    language,
                    "schedule_cutoff_line",
                    cutoff_time=window.preference_cutoff_time,
                )
            )
    return lines


def _service_label(language: str, service_key: str) -> str:
    """Return the localized service label for one schedule key."""
    return t(language, f"service_{service_key}")


def _weekday_label(language: str, weekday: str, fallback: str) -> str:
    """Return the localized label for one weekday key when available."""
    translation_key = f"weekday_{weekday}"
    try:
        return t(language, translation_key)
    except KeyError:
        return fallback


def _meal_label(language: str, meal_type: str) -> str:
    """Return the localized human-readable meal label."""
    return t(language, "meal_lunch" if meal_type == "lunch" else "meal_dinner")
