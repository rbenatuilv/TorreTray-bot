"""Typed models used by the Telegram bot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from torretray_bot.localization import t


def _pretty_label(value: str) -> str:
    """Return a user-facing label with normalized spacing and sentence casing."""
    collapsed = " ".join(value.split())
    if not collapsed:
        return collapsed
    return collapsed[:1].upper() + collapsed[1:].lower()


@dataclass(frozen=True)
class BackendUser:
    """One backend user linked to a Telegram account."""

    id: int
    name: str
    telegram_id: str | None
    preferred_language: str

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "BackendUser":
        """Build a typed user from a backend JSON payload."""
        return cls(
            id=int(payload["id"]),
            name=str(payload["name"]),
            telegram_id=(
                str(payload["telegram_id"])
                if payload.get("telegram_id") is not None
                else None
            ),
            preferred_language=str(payload.get("preferred_language", "en")),
        )


@dataclass(frozen=True)
class MenuOption:
    """One dish option in a menu section."""

    raw_dish: str
    dish: str
    flags: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "MenuOption":
        """Build a typed menu option from a backend JSON payload."""
        raw_dish = str(payload["dish"])
        return cls(
            raw_dish=raw_dish,
            dish=_pretty_label(raw_dish),
            flags=(
                _pretty_label(str(payload["flags"]))
                if payload.get("flags") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class MenuSection:
    """One menu section shown in the preference flow."""

    raw_name: str
    name: str
    options: list[MenuOption]

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "MenuSection":
        """Build a typed menu section from a backend JSON payload."""
        raw_options = payload.get("options", [])
        raw_name = str(payload["name"])
        return cls(
            raw_name=raw_name,
            name=_pretty_label(raw_name),
            options=[
                MenuOption.from_payload(option)
                for option in raw_options
                if isinstance(option, dict)
            ],
        )


@dataclass(frozen=True)
class PreferenceContext:
    """Bot-facing summary of whether preferences can still be set."""

    meal_status_id: int | None
    date: str
    meal_type: str
    menu_available: bool
    reservation_found: bool
    reservation_type: str | None
    printed: bool | None
    cutoff_time: str
    can_set_preferences: bool
    blocked_reason: str | None
    blocked_message: str | None
    sections: list[MenuSection]

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "PreferenceContext":
        """Build a typed context from a backend JSON payload."""
        raw_sections = payload.get("sections", [])
        return cls(
            meal_status_id=(
                int(payload["meal_status_id"])
                if payload.get("meal_status_id") is not None
                else None
            ),
            date=str(payload["date"]),
            meal_type=str(payload["meal_type"]),
            menu_available=bool(payload["menu_available"]),
            reservation_found=bool(payload["reservation_found"]),
            reservation_type=(
                str(payload["reservation_type"])
                if payload.get("reservation_type") is not None
                else None
            ),
            printed=(
                bool(payload["printed"]) if payload.get("printed") is not None else None
            ),
            cutoff_time=str(payload["cutoff_time"]),
            can_set_preferences=bool(payload["can_set_preferences"]),
            blocked_reason=(
                str(payload["blocked_reason"])
                if payload.get("blocked_reason") is not None
                else None
            ),
            blocked_message=(
                str(payload["blocked_message"])
                if payload.get("blocked_message") is not None
                else None
            ),
            sections=[
                MenuSection.from_payload(section)
                for section in raw_sections
                if isinstance(section, dict)
            ],
        )


@dataclass(frozen=True)
class CurrentPreferences:
    """Current saved preferences for one meal, if any."""

    meal_status_id: int | None
    date: str
    meal_type: str
    reservation_found: bool
    reservation_type: str | None
    printed: bool | None
    preferences: dict[str, object] | None

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "CurrentPreferences":
        """Build the current-preferences view model from backend JSON."""
        preferences = payload.get("preferences")
        return cls(
            meal_status_id=(
                int(payload["meal_status_id"])
                if payload.get("meal_status_id") is not None
                else None
            ),
            date=str(payload["date"]),
            meal_type=str(payload["meal_type"]),
            reservation_found=bool(payload["reservation_found"]),
            reservation_type=(
                str(payload["reservation_type"])
                if payload.get("reservation_type") is not None
                else None
            ),
            printed=(
                bool(payload["printed"]) if payload.get("printed") is not None else None
            ),
            preferences=preferences if isinstance(preferences, dict) else None,
        )


@dataclass(frozen=True)
class MealScheduleWindow:
    """One backend-defined service window for one date."""

    service_key: str
    label: str
    meal_type: str
    reservation_type: str
    start_time: str
    end_time: str
    preference_cutoff_time: str | None

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "MealScheduleWindow":
        """Build one schedule window from backend JSON."""
        return cls(
            service_key=str(payload["service_key"]),
            label=str(payload["label"]),
            meal_type=str(payload["meal_type"]),
            reservation_type=str(payload["reservation_type"]),
            start_time=str(payload["start_time"]),
            end_time=str(payload["end_time"]),
            preference_cutoff_time=(
                str(payload["preference_cutoff_time"])
                if payload.get("preference_cutoff_time") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class DailyMealSchedule:
    """One day's schedule returned by the backend."""

    date: date
    weekday: str
    weekday_label: str
    windows: list[MealScheduleWindow]

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "DailyMealSchedule":
        """Build one daily schedule from backend JSON."""
        raw_windows = payload.get("windows", [])
        return cls(
            date=date.fromisoformat(str(payload["date"])),
            weekday=str(payload["weekday"]),
            weekday_label=str(payload["weekday_label"]),
            windows=[
                MealScheduleWindow.from_payload(window)
                for window in raw_windows
                if isinstance(window, dict)
            ],
        )


@dataclass(frozen=True)
class WeekdayMealSchedule:
    """One weekday template returned by the backend."""

    weekday: str
    weekday_label: str
    windows: list[MealScheduleWindow]

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "WeekdayMealSchedule":
        """Build one weekday template from backend JSON."""
        raw_windows = payload.get("windows", [])
        return cls(
            weekday=str(payload["weekday"]),
            weekday_label=str(payload["weekday_label"]),
            windows=[
                MealScheduleWindow.from_payload(window)
                for window in raw_windows
                if isinstance(window, dict)
            ],
        )


@dataclass
class ScheduleEditSession:
    """In-memory admin flow state for editing one meal schedule window."""

    weekday: str | None = None
    service_key: str | None = None
    start_time: str | None = None
    awaiting_time_field: str | None = None


@dataclass(frozen=True)
class SectionSelection:
    """One user choice for a menu section."""

    section_name: str
    selected: bool
    selected_dish: str | None
    no_specific_preference: bool
    display_section_name: str
    display_selected_dish: str | None
    available_options: list[str]

    def to_payload(self) -> dict[str, object]:
        """Convert the selection into the backend request shape."""
        return {
            "section_name": self.section_name,
            "selected": self.selected,
            "selected_dish": self.selected_dish,
            "no_specific_preference": self.no_specific_preference,
            "available_options": self.available_options,
        }


@dataclass
class PreferenceSession:
    """In-memory Telegram conversation state for one meal preference flow."""

    meal_status_id: int
    meal_type: str
    meal_date: str
    sections: list[MenuSection]
    current_index: int = 0
    selections: dict[int, SectionSelection] = field(default_factory=dict)

    def current_section(self) -> MenuSection | None:
        """Return the section currently being asked to the user."""
        if self.current_index >= len(self.sections):
            return None
        return self.sections[self.current_index]

    def record_selection(
        self,
        *,
        section_index: int,
        selected: bool,
        selected_dish: str | None,
        no_specific_preference: bool,
        selected_display_dish: str | None,
    ) -> SectionSelection:
        """Store one answer and advance to the next section."""
        section = self.sections[section_index]
        selection = SectionSelection(
            section_name=section.raw_name,
            selected=selected,
            selected_dish=selected_dish,
            no_specific_preference=no_specific_preference,
            display_section_name=section.name,
            display_selected_dish=selected_display_dish,
            available_options=[option.raw_dish for option in section.options],
        )
        self.selections[section_index] = selection
        self.current_index = section_index + 1
        return selection

    def is_complete(self) -> bool:
        """Return whether all menu sections have been answered."""
        return self.current_index >= len(self.sections)

    def build_summary_lines(self, language: str = "en") -> list[str]:
        """Return a compact human-readable summary of the chosen preferences."""
        lines: list[str] = []
        for index, section in enumerate(self.sections):
            selection = self.selections[index]
            chosen_value = (
                selection.display_selected_dish
                if selection.selected and selection.display_selected_dish is not None
                else t(language, "summary_no_preference")
                if selection.selected and selection.no_specific_preference
                else f"{t(language, 'button_no')} {section.name}"
            )
            lines.append(f"• {section.name}: {chosen_value}")
        return lines

    def to_update_payload(self) -> dict[str, object]:
        """Convert the full session into the backend update payload."""
        ordered_selections = [
            self.selections[index] for index in range(len(self.sections))
        ]
        return {
            "sections": [selection.to_payload() for selection in ordered_selections],
        }
