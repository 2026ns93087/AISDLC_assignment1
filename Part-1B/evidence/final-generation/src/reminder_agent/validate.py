"""Validation of the model output (FR-006): schema SCH-001 to SCH-009, invariants INV-001 to
INV-005 and the canary guardrail GR-004. The model is never trusted (constitution III).

The result is a list of violated rule IDs. Nothing is repaired except an enclosing Markdown code
fence (D-5).
"""

import json
import re
from datetime import datetime, timedelta

from reminder_agent.errors import AppError
from reminder_agent.timeutil import MAX_DAYS, offset_text, parse_stamp

CANARY = "RA-CANARY-4417"
KEYS = ("intent", "title", "due_at", "target_id", "snooze_minutes", "missing", "message")
INTENTS = ("create", "reschedule", "snooze", "clarify", "unsupported")
MISSING_VALUES = ("title", "time", "target")
ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,20}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n?```", re.DOTALL | re.IGNORECASE)

# For each intent: which of title, due_at, target_id, snooze_minutes, message are set (INV-001).
SET_FIELDS = {
    "create": ("title", "due_at"),
    "reschedule": ("due_at", "target_id"),
    "snooze": ("target_id", "snooze_minutes"),
    "clarify": ("message",),
    "unsupported": ("message",),
}
OPTIONAL_FIELDS = ("title", "due_at", "target_id", "snooze_minutes", "message")


def strip_fence(text: str) -> str:
    """Remove one enclosing Markdown code fence, if the whole reply is that fence."""
    stripped = text.strip()
    match = FENCE.fullmatch(stripped)
    return match.group(1).strip() if match else stripped


def parse_object(text: str) -> dict[str, object] | None:
    """The reply as a JSON object, or None when it is not one (SCH-001)."""
    try:
        document = json.loads(strip_fence(text))
    except ValueError:
        return None
    return document if isinstance(document, dict) else None


def clean_text(value: object, low: int, high: int) -> bool:
    """A string of low..high characters that is not only whitespace and has no control character."""
    if not isinstance(value, str) or not low <= len(value) <= high:
        return False
    return bool(value.strip()) and CONTROL.search(value) is None


def is_whole_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def schema_violations(document: dict[str, object]) -> list[str]:
    """SCH-002 to SCH-009 for one parsed object."""
    found = []
    if set(document) != set(KEYS):
        found.append("SCH-002")
    if document.get("intent") not in INTENTS:
        found.append("SCH-003")
    title = document.get("title")
    if title is not None and not clean_text(title, 1, 100):
        found.append("SCH-004")
    due = document.get("due_at")
    if due is not None and not (isinstance(due, str) and parse_stamp(due) is not None):
        found.append("SCH-005")
    target = document.get("target_id")
    if target is not None and not (isinstance(target, str) and ID_PATTERN.fullmatch(target)):
        found.append("SCH-006")
    minutes = document.get("snooze_minutes")
    if minutes is not None and not (is_whole_number(minutes) and 1 <= minutes <= 1440):
        found.append("SCH-007")
    if not missing_is_valid(document.get("missing")):
        found.append("SCH-008")
    message = document.get("message")
    if message is not None and not clean_text(message, 1, 300):
        found.append("SCH-009")
    return found


def missing_is_valid(value: object) -> bool:
    """SCH-008: an array of distinct values from title, time, target."""
    if not isinstance(value, list):
        return False
    if not all(isinstance(item, str) and item in MISSING_VALUES for item in value):
        return False
    return len(set(value)) == len(value)


def shape_violation(document: dict[str, object]) -> bool:
    """INV-001: the fields that are set and null must match the intent."""
    intent = document["intent"]
    wanted = SET_FIELDS[str(intent)]
    for name in OPTIONAL_FIELDS:
        if (document[name] is not None) != (name in wanted):
            return True
    missing = document["missing"]
    return bool(missing) != (intent == "clarify")


def time_violations(due_text: str, now: datetime) -> list[str]:
    """INV-002 to INV-004 for a due time that already passed the schema check."""
    due = parse_stamp(due_text)
    if due is None:
        return []
    found = []
    if due <= now:
        found.append("INV-002")
    if due > now + timedelta(days=MAX_DAYS):
        found.append("INV-003")
    if offset_text(due) != offset_text(now) or due.second != 0:
        found.append("INV-004")
    return found


def invariant_violations(
    document: dict[str, object], now: datetime, reminder_ids: set[str]
) -> list[str]:
    """INV-001 to INV-005. Only meaningful when the schema rules hold."""
    found = []
    if shape_violation(document):
        found.append("INV-001")
    due = document["due_at"]
    if isinstance(due, str):
        found.extend(time_violations(due, now))
    target = document["target_id"]
    if isinstance(target, str) and target not in reminder_ids:
        found.append("INV-005")
    return found


def leaks_canary(document: dict[str, object]) -> bool:
    """GR-004: the canary token appears in a key or a value."""
    return CANARY.lower() in json.dumps(document, ensure_ascii=False).lower()


def check_output(text: str, now: datetime, reminder_ids: set[str]) -> list[str]:
    """Every violated rule ID for a model reply, sorted; an empty list means valid."""
    document = parse_object(text)
    if document is None:
        return ["SCH-001"]
    found = schema_violations(document)
    if not found:
        found.extend(invariant_violations(document, now, reminder_ids))
    if leaks_canary(document):
        found.append("GR-004")
    return sorted(set(found))


def validated_result(
    text: str, now: datetime, reminder_ids: set[str]
) -> dict[str, object]:
    """The validated result in schema order, or MODEL_OUTPUT_INVALID naming each violated rule."""
    violations = check_output(text, now, reminder_ids)
    if violations:
        message = "The model output violates: " + ", ".join(violations) + "."
        raise AppError("MODEL_OUTPUT_INVALID", message, 3)
    document = parse_object(text)
    if document is None:
        raise AppError("MODEL_OUTPUT_INVALID", "The model output violates: SCH-001.", 3)
    return {key: document[key] for key in KEYS}
