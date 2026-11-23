"""Prompt building (FR-005): a pure function of the reference time, reminders and request."""

import json
import re
from datetime import datetime
from pathlib import Path

from reminder_agent.errors import AppError
from reminder_agent.timeutil import (
    calendar_lines,
    format_stamp,
    latest_allowed,
    offset_text,
    weekday_name,
)

SYSTEM_PATH = Path(__file__).resolve().parents[2] / "prompts" / "system.md"
REQUEST_TAG = re.compile(r"<\s*/?\s*request\s*>", re.IGNORECASE)
Reminder = dict[str, str]


def load_system_prompt(path: Path = SYSTEM_PATH) -> str:
    """The system instruction text. A missing file is a configuration error."""
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise AppError("INVALID_CONFIG", "The system prompt file cannot be read.", 3) from error


def neutralise(text: str) -> str:
    """Make request tags inside the request harmless so the user cannot close the data block."""
    return REQUEST_TAG.sub("[request-tag]", text)


def build_user_message(now: datetime, reminders: list[Reminder], request: str) -> str:
    """The user message: facts first, then the request between `<request>` tags."""
    lines = [
        f"Reference time: {format_stamp(now)} ({weekday_name(now)})",
        f"UTC offset: {offset_text(now)}",
        f"Latest allowed time: {format_stamp(latest_allowed(now))}",
        "Calendar (today and the next 14 days):",
        *calendar_lines(now),
        "Existing reminders (JSON):",
        json.dumps(reminders),
        "<request>",
        neutralise(request),
        "</request>",
    ]
    return "\n".join(lines)
