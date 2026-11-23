"""The reminders input file (FR-004): a JSON array of at most 20 reminders."""

import json
import re
from pathlib import Path

from reminder_agent.errors import AppError
from reminder_agent.timeutil import parse_stamp

MAX_REMINDERS = 20
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,20}")
EXPECTED_KEYS = {"id", "title", "due_at"}
Reminder = dict[str, str]


def invalid(reason: str) -> AppError:
    return AppError("INVALID_REMINDERS", f"The reminders file is not valid: {reason}.")


def check_item(item: object, seen: set[str]) -> Reminder:
    """One reminder: exactly the three keys, valid values, a unique id."""
    if not isinstance(item, dict) or set(item) != EXPECTED_KEYS:
        raise invalid("each item needs exactly id, title and due_at")
    reminder_id, title, due = item["id"], item["title"], item["due_at"]
    if not isinstance(reminder_id, str) or ID_PATTERN.fullmatch(reminder_id) is None:
        raise invalid("bad id")
    if reminder_id in seen:
        raise invalid("duplicate id")
    if not isinstance(title, str) or not 1 <= len(title) <= 100:
        raise invalid("bad title")
    if not isinstance(due, str) or parse_stamp(due) is None:
        raise invalid("bad due_at")
    seen.add(reminder_id)
    return {"id": reminder_id, "title": title, "due_at": due}


def load_reminders(path: str | None) -> list[Reminder]:
    """The validated reminders; no option means an empty list."""
    if path is None:
        return []
    try:
        document = json.loads(Path(path).read_bytes().decode("utf-8-sig"))
    except (OSError, ValueError) as error:
        raise invalid("the file cannot be read as JSON") from error
    if not isinstance(document, list) or len(document) > MAX_REMINDERS:
        raise invalid(f"it must be an array of at most {MAX_REMINDERS} items")
    seen: set[str] = set()
    return [check_item(item, seen) for item in document]
