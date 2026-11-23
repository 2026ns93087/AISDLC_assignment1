"""Time helpers: the one timestamp format, the weekday table and the 366-day limit.

Nothing here reads the clock (constitution VII). Weekday names are a fixed English table so the
output does not depend on the operating-system language.
"""

import re
from datetime import datetime, timedelta, timezone

from reminder_agent.errors import AppError

MAX_DAYS = 366
CALENDAR_DAYS = 14
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
STAMP = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})([+-])([0-9]{2}):([0-9]{2})"
)


def parse_stamp(text: str) -> datetime | None:
    """A `YYYY-MM-DDTHH:MM:SS+HH:MM` timestamp as an aware datetime, or None when not valid."""
    match = STAMP.fullmatch(text)
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    offset_hours, offset_minutes = int(match.group(8)), int(match.group(9))
    if offset_hours > 23 or offset_minutes > 59:
        return None
    span = timedelta(hours=offset_hours, minutes=offset_minutes)
    zone = timezone(-span if match.group(7) == "-" else span)
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=zone)
    except ValueError:
        return None


def format_stamp(moment: datetime) -> str:
    """The timestamp format of FR-003 (whole seconds, numeric offset)."""
    return moment.replace(microsecond=0).isoformat()


def offset_text(moment: datetime) -> str:
    """The UTC offset of an aware datetime as `+HH:MM` or `-HH:MM`."""
    offset = moment.utcoffset()
    minutes = 0 if offset is None else int(offset.total_seconds() // 60)
    sign = "-" if minutes < 0 else "+"
    hours, rest = divmod(abs(minutes), 60)
    return f"{sign}{hours:02d}:{rest:02d}"


def weekday_name(moment: datetime) -> str:
    return WEEKDAYS[moment.weekday()]


def latest_allowed(now: datetime) -> datetime:
    """The latest due time that INV-003 accepts."""
    return now + timedelta(days=MAX_DAYS)


def parse_now(text: str) -> datetime:
    """Parse `--now` (FR-003). The 366-day limit must be computable, else the value is rejected."""
    message = "--now must look like 2026-03-10T09:00:00+00:00 and be a real date and time."
    moment = parse_stamp(text)
    if moment is None:
        raise AppError("INVALID_NOW", message)
    try:
        latest_allowed(moment)
        moment + timedelta(days=CALENDAR_DAYS)
    except OverflowError as error:
        raise AppError("INVALID_NOW", message) from error
    return moment


def calendar_lines(now: datetime) -> list[str]:
    """Today and the following 14 days, one `date weekday` line each."""
    lines = []
    for step in range(CALENDAR_DAYS + 1):
        day = now + timedelta(days=step)
        suffix = " (today)" if step == 0 else ""
        lines.append(f"{day.date().isoformat()} {weekday_name(day)}{suffix}")
    return lines
