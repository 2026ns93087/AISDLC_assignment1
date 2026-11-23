"""US-006: the application checks the model output (FR-006). AC-014 to AC-017.

Each case is a reply that the fake model returns; the program must refuse it with
MODEL_OUTPUT_INVALID (exit 3), print nothing on stdout, and name every violated rule.
"""

import json

import pytest
from support import CANARY, Sandbox, create_reply, exactly, reply

REQUEST = "Remind me to call the dentist tomorrow at 3pm"
R1 = [{"id": "r1", "title": "Dentist", "due_at": "2026-03-12T10:00:00+00:00"}]
SOON = "2026-03-11T15:00:00+00:00"


def rejected(box: Sandbox, text: str, rule: str, reminders: bool = False) -> None:
    """The reply is refused with MODEL_OUTPUT_INVALID and the message names the rule."""
    box.fake.reply_with(text)
    args = []
    if reminders:
        args += ["--reminders", str(box.write("reminders.json", json.dumps(R1)))]
    run = box.run(*args, REQUEST)
    assert run.error_code(3) == "MODEL_OUTPUT_INVALID"
    assert rule in run.error_message()


def with_field(**changes: object) -> str:
    return json.dumps({**create_reply(), **changes})


def without_key(name: str) -> str:
    document = create_reply()
    del document[name]
    return json.dumps(document)


def test_ac_014_not_json(box: Sandbox) -> None:
    """AC-014: a reply that is not JSON violates SCH-001."""
    rejected(box, "Sure! I will remind you tomorrow.", "SCH-001")


@pytest.mark.parametrize("text", ["[]", "[1, 2]", '"create"', "42", "null", "true"])
def test_ac_014_json_that_is_not_an_object(box: Sandbox, text: str) -> None:
    """AC-014: a JSON array, string, number or null violates SCH-001."""
    rejected(box, text, "SCH-001")


@pytest.mark.parametrize("name", ["intent", "title", "due_at", "message", "missing"])
def test_ac_014_missing_key(box: Sandbox, name: str) -> None:
    """AC-014: a missing key violates SCH-002."""
    rejected(box, without_key(name), "SCH-002")


def test_ac_014_extra_key(box: Sandbox) -> None:
    """AC-014: an extra key violates SCH-002."""
    rejected(box, with_field(confidence=0.9), "SCH-002")


@pytest.mark.parametrize("intent", ["delete", "CREATE", "", None, 3])
def test_ac_014_unknown_intent(box: Sandbox, intent: object) -> None:
    """AC-014: an intent outside the five allowed values violates SCH-003."""
    rejected(box, with_field(intent=intent), "SCH-003")


@pytest.mark.parametrize("title", ["x" * 101, "", "   ", "bad\ttitle", "a\nb", 7, ["a"]])
def test_ac_014_bad_title(box: Sandbox, title: object) -> None:
    """AC-014: a title that is too long, empty, blank, has a control character or is no string."""
    rejected(box, with_field(title=title), "SCH-004")


@pytest.mark.parametrize(
    "due",
    [
        "tomorrow",
        "2026-03-11 15:00:00+00:00",
        "2026-03-11T15:00:00Z",
        "2026-03-11T15:00:00",
        "2026-02-30T15:00:00+00:00",
        "2026-03-11T25:00:00+00:00",
        "2026-03-11T15:00+00:00",
        1773237600,
    ],
)
def test_ac_014_malformed_due_at(box: Sandbox, due: object) -> None:
    """AC-014: a malformed or impossible due_at violates SCH-005."""
    rejected(box, with_field(due_at=due), "SCH-005")


@pytest.mark.parametrize("target", ["bad id", "a" * 21, "", 5])
def test_ac_014_bad_target_id(box: Sandbox, target: object) -> None:
    """AC-014: a malformed target_id violates SCH-006."""
    document = reply(intent="snooze", target_id=target, snooze_minutes=5)
    rejected(box, json.dumps(document), "SCH-006")


@pytest.mark.parametrize("minutes", [True, False, 0, 1441, -5, 5.5, "15"])
def test_ac_014_bad_snooze_minutes(box: Sandbox, minutes: object) -> None:
    """AC-014: a boolean, 0, 1441, negative, fractional or string violates SCH-007."""
    document = reply(intent="snooze", target_id="r1", snooze_minutes=minutes)
    rejected(box, json.dumps(document), "SCH-007", reminders=True)


@pytest.mark.parametrize(
    "missing",
    [["date"], ["time", "time"], "time", None, [1], [["time"]]],
)
def test_ac_014_bad_missing_value(box: Sandbox, missing: object) -> None:
    """AC-014: an unknown, repeated or mistyped missing list violates SCH-008."""
    rejected(box, with_field(missing=missing), "SCH-008")


@pytest.mark.parametrize("message", ["x" * 301, "", "   ", "a\x07b", 3])
def test_ac_014_bad_message(box: Sandbox, message: object) -> None:
    """AC-014: a bad message (length, blank, control character, type) violates SCH-009."""
    document = reply(intent="unsupported", message=message)
    rejected(box, json.dumps(document), "SCH-009")


def test_ac_014_boundary_lengths_are_accepted(box: Sandbox) -> None:
    """AC-014: a 100-character title and a 300-character message are accepted."""
    box.fake.reply_json({**create_reply(), "title": "t" * 100})
    assert box.run(REQUEST).result()["title"] == "t" * 100
    document = reply(intent="unsupported", message="m" * 300)
    box.fake.reply_json(document)
    assert box.run(REQUEST).result()["message"] == "m" * 300


def test_ac_015_fields_must_match_the_intent(box: Sandbox) -> None:
    """AC-015: a create reply that also carries a target_id violates INV-001."""
    rejected(box, with_field(target_id="r1"), "INV-001", reminders=True)


@pytest.mark.parametrize(
    "document",
    [
        reply(intent="create", title="x", due_at=None),
        reply(intent="create", due_at="2026-03-11T15:00:00+00:00"),
        reply(intent="create", title="x", due_at="2026-03-11T15:00:00+00:00", message="hi"),
        reply(intent="reschedule", target_id="r1", title="x", due_at=SOON),
        reply(intent="reschedule", target_id="r1"),
        reply(intent="snooze", target_id="r1", snooze_minutes=5, due_at=SOON),
        reply(intent="snooze", target_id="r1"),
        reply(intent="clarify", message="When?"),
        reply(intent="clarify", missing=["time"]),
        reply(intent="clarify", missing=["time"], message="When?", title="x"),
        reply(intent="unsupported"),
        reply(intent="unsupported", message="No", missing=["time"]),
    ],
)
def test_ac_015_wrong_field_pattern_for_the_intent(box: Sandbox, document: dict) -> None:
    """AC-015: set and null fields that do not match the intent violate INV-001."""
    rejected(box, json.dumps(document), "INV-001", reminders=True)


@pytest.mark.parametrize(
    "due",
    ["2026-03-10T09:00:00+00:00", "2026-03-10T08:59:00+00:00", "2025-01-01T09:00:00+00:00"],
)
def test_ac_015_due_time_not_in_the_future(box: Sandbox, due: str) -> None:
    """AC-015: a due_at equal to or before the reference time violates INV-002."""
    rejected(box, with_field(due_at=due), "INV-002")


def test_ac_015_due_time_beyond_366_days(box: Sandbox) -> None:
    """AC-015: a due_at after reference + 366 days violates INV-003."""
    rejected(box, with_field(due_at="2027-03-11T09:01:00+00:00"), "INV-003")


def test_ac_015_due_time_exactly_366_days_ahead_is_accepted(box: Sandbox) -> None:
    """AC-015: a due_at exactly 366 days ahead is accepted."""
    document = {**create_reply(), "due_at": "2027-03-11T09:00:00+00:00"}
    box.fake.reply_json(document)
    assert box.run(REQUEST).result()["due_at"] == "2027-03-11T09:00:00+00:00"


@pytest.mark.parametrize("due", ["2026-03-11T15:00:00+01:00", "2026-03-11T15:00:00-05:00"])
def test_ac_015_due_time_with_another_offset(box: Sandbox, due: str) -> None:
    """AC-015: a due_at with another UTC offset violates INV-004."""
    rejected(box, with_field(due_at=due), "INV-004")


def test_ac_015_due_time_with_nonzero_seconds(box: Sandbox) -> None:
    """AC-015: a due_at with seconds other than 00 violates INV-004."""
    rejected(box, with_field(due_at="2026-03-11T15:00:30+00:00"), "INV-004")


@pytest.mark.parametrize("intent", ["reschedule", "snooze"])
def test_ac_015_target_not_in_the_supplied_reminders(box: Sandbox, intent: str) -> None:
    """AC-015: a target_id that is not a supplied reminder violates INV-005."""
    due = "2026-03-12T09:00:00+00:00" if intent == "reschedule" else None
    minutes = 10 if intent == "snooze" else None
    document = reply(intent=intent, target_id="zzz", due_at=due, snooze_minutes=minutes)
    rejected(box, json.dumps(document), "INV-005", reminders=True)


def test_ac_015_target_with_no_reminders_supplied(box: Sandbox) -> None:
    """AC-015: with no reminders supplied, any target_id violates INV-005."""
    document = reply(intent="snooze", target_id="r1", snooze_minutes=10)
    rejected(box, json.dumps(document), "INV-005")


def test_ac_015_every_violated_rule_is_named(box: Sandbox) -> None:
    """AC-015: when several rules fail, the message names each of them."""
    box.fake.reply_with(with_field(due_at="2026-03-09T09:00:30+01:00", target_id="r1"))
    message = box.run(REQUEST).error_message()
    for rule in ("INV-001", "INV-002", "INV-004", "INV-005"):
        assert rule in message


@pytest.mark.parametrize("where", ["title", "message", "key"])
def test_ac_016_canary_in_the_output(box: Sandbox, where: str) -> None:
    """AC-016: the canary token anywhere in the output violates GR-004."""
    if where == "title":
        text = with_field(title=f"note {CANARY}")
    elif where == "message":
        text = json.dumps(reply(intent="unsupported", message=f"secret is {CANARY.lower()}"))
    else:
        text = json.dumps({**create_reply(), CANARY: 1})
    box.fake.reply_with(text)
    run = box.run(REQUEST)
    assert run.error_code(3) == "MODEL_OUTPUT_INVALID"
    assert "GR-004" in run.error_message()
    assert CANARY not in run.err


def test_ac_017_json_fence_is_accepted(box: Sandbox) -> None:
    """AC-017: a reply wrapped in a ```json fence is accepted and printed normally."""
    box.fake.reply_with("```json\n" + json.dumps(create_reply()) + "\n```")
    run = box.run(REQUEST)
    assert run.code == 0
    assert run.out == exactly(create_reply())


def test_ac_017_plain_fence_is_accepted(box: Sandbox) -> None:
    """AC-017: a reply wrapped in a plain ``` fence is accepted."""
    box.fake.reply_with("```\n" + json.dumps(create_reply()) + "\n```")
    assert box.run(REQUEST).out == exactly(create_reply())


@pytest.mark.parametrize(
    "wrap",
    [
        "Here you go: {}",
        "{}\nHope this helps!",
        "```json\n{}\n``` extra",
        "{}{}",
    ],
)
def test_ac_017_text_around_the_object_is_rejected(box: Sandbox, wrap: str) -> None:
    """AC-017: text before or after the object, or two objects, violates SCH-001."""
    body = json.dumps(create_reply())
    rejected(box, wrap.replace("{}", body), "SCH-001")
