"""HTTP client for the TorreTray backend API."""

from __future__ import annotations

from typing import Any

import httpx

from torretray_bot.models import BackendUser, CurrentPreferences, PreferenceContext


class BackendApiError(Exception):
    """Raised when the backend cannot fulfill a bot request."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TorreTrayBackendClient:
    """Async wrapper around the backend endpoints used by the bot."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def get_registered_user(self, telegram_id: str) -> BackendUser | None:
        """Return the backend user linked to the provided Telegram id."""
        payload = await self._request(
            "GET",
            f"/users/by-telegram-id/{telegram_id}",
            allow_not_found=True,
        )
        if payload is None:
            return None
        return BackendUser.from_payload(payload)

    async def register_telegram_user(
        self,
        *,
        name: str,
        telegram_id: str,
    ) -> BackendUser:
        """Link a Telegram account to an existing backend user by name."""
        payload = await self._request(
            "POST",
            "/users/register-telegram",
            json={
                "name": name,
                "telegram_id": telegram_id,
            },
        )
        return BackendUser.from_payload(payload)

    async def update_user_language(
        self,
        *,
        user_id: int,
        preferred_language: str,
    ) -> BackendUser:
        """Persist the preferred language for one backend user."""
        payload = await self._request(
            "PATCH",
            f"/users/{user_id}/language",
            json={"preferred_language": preferred_language},
        )
        return BackendUser.from_payload(payload)

    async def unregister_telegram_user(
        self,
        *,
        user_id: int,
        telegram_id: str,
    ) -> BackendUser:
        """Remove the Telegram identifier from one backend user."""
        payload = await self._request(
            "PATCH",
            f"/users/{user_id}/telegram-id/unregister",
            json={"telegram_id": telegram_id},
        )
        return BackendUser.from_payload(payload)

    async def get_preference_context(
        self,
        *,
        user_id: int,
        meal_type: str,
    ) -> PreferenceContext:
        """Return the backend context that drives the preference flow."""
        payload = await self._request(
            "GET",
            "/meal-status/preferences/context",
            params={
                "user_id": user_id,
                "meal_type": meal_type,
            },
        )
        return PreferenceContext.from_payload(payload)

    async def get_current_preferences(
        self,
        *,
        user_id: int,
        meal_type: str,
    ) -> CurrentPreferences:
        """Return today's currently saved preferences for one meal."""
        payload = await self._request(
            "GET",
            "/meal-status/preferences/current",
            params={
                "user_id": user_id,
                "meal_type": meal_type,
            },
        )
        return CurrentPreferences.from_payload(payload)

    async def update_preferences(
        self,
        *,
        meal_status_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist the final preferences for a meal-status row."""
        response_payload = await self._request(
            "PATCH",
            f"/meal-status/{meal_status_id}/preferences",
            json=payload,
        )
        return response_payload or {}

    async def clear_preferences(
        self,
        *,
        meal_status_id: int,
    ) -> dict[str, Any]:
        """Clear any previously saved preferences for a meal-status row."""
        response_payload = await self._request(
            "DELETE",
            f"/meal-status/{meal_status_id}/preferences",
        )
        return response_payload or {}

    async def _request(
        self,
        method: str,
        path: str,
        *,
        allow_not_found: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Perform one backend request and normalize backend errors."""
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise BackendApiError("Could not reach the TorreTray backend API.") from exc

        if allow_not_found and response.status_code == 404:
            return None
        if response.is_error:
            raise BackendApiError(
                self._extract_error_message(response),
                status_code=response.status_code,
            )

        payload = response.json()
        if not isinstance(payload, dict):
            raise BackendApiError("The backend returned an unexpected response.")
        return payload

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        """Extract the most useful error detail from a backend response."""
        try:
            payload = response.json()
        except ValueError:
            return f"Backend error {response.status_code}."

        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, str) and detail.strip():
            return detail
        return f"Backend error {response.status_code}."
