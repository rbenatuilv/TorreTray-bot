"""Package entrypoint for `python -m torretray_bot`."""

from __future__ import annotations

import argparse
from datetime import date, datetime

from torretray_bot.app import main


def _parse_test_time(value: str) -> date:
    """Accept an ISO date or datetime and return its date portion."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        try:
            return datetime.fromisoformat(value).date()
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "Expected YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS for --test-time."
            ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the TorreTray Telegram bot.")
    parser.add_argument(
        "--test-time",
        "--testtime",
        dest="test_time",
        type=_parse_test_time,
        help="Override the effective date for bot requests using ISO date or datetime.",
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    main(test_date_override=args.test_time)
