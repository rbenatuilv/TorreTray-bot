"""Telegram inline keyboards used by the bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from torretray_bot.localization import t
from torretray_bot.models import MenuSection


def meal_type_keyboard(language: str) -> InlineKeyboardMarkup:
    """Return the keyboard that starts the lunch/dinner flow."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🍽️ {t(language, 'button_lunch')}",
                    callback_data="meal:lunch",
                ),
                InlineKeyboardButton(
                    f"🌙 {t(language, 'button_dinner')}",
                    callback_data="meal:dinner",
                ),
            ]
        ]
    )


def view_preferences_keyboard(language: str) -> InlineKeyboardMarkup:
    """Return the keyboard used to inspect current lunch/dinner preferences."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"👀 {t(language, 'button_lunch')}",
                    callback_data="view:lunch",
                ),
                InlineKeyboardButton(
                    f"👀 {t(language, 'button_dinner')}",
                    callback_data="view:dinner",
                ),
            ]
        ]
    )


def clear_preferences_keyboard(language: str) -> InlineKeyboardMarkup:
    """Return the keyboard used to clear saved lunch/dinner preferences."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🗑️ {t(language, 'button_lunch')}",
                    callback_data="clearmeal:lunch",
                ),
                InlineKeyboardButton(
                    f"🗑️ {t(language, 'button_dinner')}",
                    callback_data="clearmeal:dinner",
                ),
            ]
        ]
    )


def language_keyboard() -> InlineKeyboardMarkup:
    """Return the keyboard used to select English or Italian."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("English", callback_data="lang:en"),
                InlineKeyboardButton("Italiano", callback_data="lang:it"),
            ]
        ]
    )


def unregister_keyboard(language: str) -> InlineKeyboardMarkup:
    """Return the keyboard used to confirm Telegram unlinking."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🗑️ {t(language, 'button_unregister')}",
                    callback_data="unregister:yes",
                ),
                InlineKeyboardButton(
                    f"↩️ {t(language, 'button_cancel')}",
                    callback_data="unregister:no",
                ),
            ]
        ]
    )


def section_keyboard(
    language: str,
    section_index: int,
    section: MenuSection,
) -> InlineKeyboardMarkup:
    """Return the keyboard for one menu section."""
    if len(section.options) == 1:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"✅ {t(language, 'button_yes')}",
                        callback_data=f"pick:{section_index}:0",
                    ),
                    InlineKeyboardButton(
                        f"❌ {t(language, 'button_no')}",
                        callback_data=f"skip:{section_index}",
                    ),
                ]
            ]
        )

    rows = [
        [
            InlineKeyboardButton(
                f"🍴 {option.dish}",
                callback_data=f"pick:{section_index}:{option_index}",
            )
        ]
        for option_index, option in enumerate(section.options)
    ]
    rows.append(
        [
            InlineKeyboardButton(
                f"🤷 {t(language, 'button_no_preference')}",
                callback_data=f"any:{section_index}",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                f"🚫 {t(language, 'button_no_section', section=section.name)}",
                callback_data=f"skip:{section_index}",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def confirmation_keyboard(language: str) -> InlineKeyboardMarkup:
    """Return the final confirmation keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"✅ {t(language, 'button_confirm')}",
                    callback_data="confirm:yes",
                ),
                InlineKeyboardButton(
                    f"↩️ {t(language, 'button_cancel')}",
                    callback_data="confirm:no",
                ),
            ]
        ]
    )


def clear_confirmation_keyboard(language: str, meal_type: str) -> InlineKeyboardMarkup:
    """Return the keyboard used to confirm preference clearing."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"🗑️ {t(language, 'button_confirm')}",
                    callback_data=f"clearconfirm:{meal_type}:yes",
                ),
                InlineKeyboardButton(
                    f"↩️ {t(language, 'button_cancel')}",
                    callback_data=f"clearconfirm:{meal_type}:no",
                ),
            ]
        ]
    )
