"""Layer 1: structural validation (SCH-001 to SCH-009), written independently of the application.

Applied to what the program printed. Each problem is an `Issue` with the rule ID, the expected
condition and what was observed.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

KEYS = ["intent", "title", "due_at", "target_id", "snooze_minutes", "missing", "message"]
INTENTS = {"create", "reschedule", "snooze", "clarify", "unsupported"}
MISSING_ALLOWED = {"title", "time", "target"}
STAMP_SHAPE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}")
ID_SHAPE = re.compile(r"[A-Za-z0-9_-]{1,20}")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
FENCE = re.compile(r"^```(?:json)?\s*\n(.*?)\n?```$", re.DOTALL | re.IGNORECASE)
Json = dict[str, object]


@dataclass(frozen=True)
class Issue:
    """One violated rule, for the findings list."""

    layer: int
    code: str
    expected: str
    observed: str


def real_timestamp(value: object) -> bool:
    """A string of the form YYYY-MM-DDTHH:MM:SS+HH:MM naming a real moment."""
    if not isinstance(value, str) or STAMP_SHAPE.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return False
    return True


def text_between(value: object, low: int, high: int) -> bool:
    """A non-blank string of low..high characters without control characters."""
    if not isinstance(value, str) or not low <= len(value) <= high:
        return False
    return value.strip() != "" and not CONTROL.search(value)


def whole_in_range(value: object, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def missing_list(value: object) -> bool:
    if not isinstance(value, list) or len(value) != len(set(map(str, value))):
        return False
    return all(isinstance(item, str) and item in MISSING_ALLOWED for item in value)


def nullable(check: Callable[[object], bool]) -> Callable[[object], bool]:
    return lambda value: value is None or check(value)


FIELD_RULES: list[tuple[str, str, str, Callable[[object], bool]]] = [
    ("intent", "SCH-003", "one of the five intents", lambda v: isinstance(v, str) and v in INTENTS),
    ("title", "SCH-004", "null or 1-100 clean characters",
     nullable(lambda v: text_between(v, 1, 100))),
    ("due_at", "SCH-005", "null or a real timestamp", nullable(real_timestamp)),
    ("target_id", "SCH-006", "null or an id of 1-20 safe characters",
     nullable(lambda v: isinstance(v, str) and ID_SHAPE.fullmatch(v) is not None)),
    ("snooze_minutes", "SCH-007", "null or an integer 1-1440",
     nullable(lambda v: whole_in_range(v, 1, 1440))),
    ("missing", "SCH-008", "distinct values of title, time, target", missing_list),
    ("message", "SCH-009", "null or 1-300 clean characters",
     nullable(lambda v: text_between(v, 1, 300))),
]


def strip_fence(text: str) -> str:
    stripped = text.strip()
    match = FENCE.match(stripped)
    return match.group(1).strip() if match else stripped


def parse_reply(text: str) -> tuple[Json | None, list[Issue]]:
    """Parse the program output. SCH-001 is reported when it is not exactly one JSON object."""
    try:
        document = json.loads(strip_fence(text))
    except ValueError as error:
        return None, [Issue(1, "SCH-001", "a single JSON object", f"not JSON: {error}")]
    if not isinstance(document, dict):
        kind = type(document).__name__
        return None, [Issue(1, "SCH-001", "a single JSON object", f"JSON {kind}")]
    return document, []


def check_structure(document: Json) -> list[Issue]:
    """SCH-002 to SCH-009 for a parsed object."""
    issues = []
    if list(document) != KEYS:
        issues.append(Issue(1, "SCH-002", f"keys exactly {KEYS}", f"keys {list(document)}"))
        return issues
    for name, rule, expected, check in FIELD_RULES:
        if not check(document[name]):
            observed = f"{name} = {document[name]!r}"[:200]
            issues.append(Issue(1, rule, f"{name}: {expected}", observed))
    return issues


def structure_of(text: str) -> tuple[Json | None, list[Issue]]:
    """Parse and check one program output."""
    document, issues = parse_reply(text)
    if document is None:
        return None, issues
    return document, check_structure(document)
