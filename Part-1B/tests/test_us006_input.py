"""US-006: input checks, configuration and the command line (nothing reaches the model).

AC-008 to AC-013, AC-024 and AC-025.
"""

import json
import socket

import pytest
from support import KEY, Sandbox, create_reply

REQUEST = "Remind me to call the dentist tomorrow at 3pm"
GOOD = {"id": "r1", "title": "Dentist", "due_at": "2026-03-12T10:00:00+00:00"}


def test_ac_008_empty_request_is_rejected(box: Sandbox) -> None:
    """AC-008: an empty or whitespace request gives EMPTY_REQUEST and no model call."""
    for text in ("", "   ", " \t "):
        run = box.run(text)
        assert run.error_code(1) == "EMPTY_REQUEST"
    assert box.fake.seen == []


def test_ac_009_request_length_limit(box: Sandbox) -> None:
    """AC-009: 500 characters are accepted, 501 give REQUEST_TOO_LONG with no model call."""
    box.fake.reply_json(create_reply())
    assert box.run("x" * 500).result()["intent"] == "create"
    assert len(box.fake.seen) == 1
    run = box.run("x" * 501)
    assert run.error_code(1) == "REQUEST_TOO_LONG"
    assert len(box.fake.seen) == 1


@pytest.mark.parametrize(
    "value",
    [
        "yesterday",
        "2026-03-10 09:00:00",
        "2026-03-10T09:00:00Z",
        "2026-13-45T25:61:61+00:00",
        "2026-03-10T09:00:00+99:99",
        "2026-02-30T09:00:00+00:00",
        "2026-03-10T09:00+00:00",
        "",
    ],
)
def test_ac_010_invalid_now_is_rejected(box: Sandbox, value: str) -> None:
    """AC-010: a malformed or impossible --now gives INVALID_NOW and no model call."""
    run = box.run("--now", value, REQUEST, use_now=False)
    assert run.error_code(1) == "INVALID_NOW"
    assert box.fake.seen == []


def test_ac_010_a_valid_now_with_a_negative_offset_is_accepted(box: Sandbox) -> None:
    """AC-010: a real date and time with a numeric offset is accepted."""
    document = {**create_reply(), "due_at": "2026-03-11T15:00:00-05:00"}
    box.fake.reply_json(document)
    run = box.run("--now", "2026-03-10T09:00:00-05:00", REQUEST, use_now=False)
    assert run.result() == document
    assert "Reference time: 2026-03-10T09:00:00-05:00" in box.fake.seen[0].user_text()
    assert "UTC offset: -05:00" in box.fake.seen[0].user_text()


BAD_REMINDER_FILES = {
    "not json": "this is not json",
    "an object": json.dumps(GOOD),
    "a string": '"r1"',
    "21 items": json.dumps([{**GOOD, "id": f"r{n}"} for n in range(21)]),
    "missing key": json.dumps([{"id": "r1", "title": "Dentist"}]),
    "extra key": json.dumps([{**GOOD, "note": "x"}]),
    "id with a space": json.dumps([{**GOOD, "id": "bad id"}]),
    "empty id": json.dumps([{**GOOD, "id": ""}]),
    "21-character id": json.dumps([{**GOOD, "id": "a" * 21}]),
    "numeric id": json.dumps([{**GOOD, "id": 7}]),
    "duplicate id": json.dumps([GOOD, {**GOOD, "title": "Other"}]),
    "bad due_at": json.dumps([{**GOOD, "due_at": "tomorrow"}]),
    "empty title": json.dumps([{**GOOD, "title": ""}]),
    "101-character title": json.dumps([{**GOOD, "title": "t" * 101}]),
    "item not an object": json.dumps(["r1"]),
}


@pytest.mark.parametrize("content", list(BAD_REMINDER_FILES.values()), ids=list(BAD_REMINDER_FILES))
def test_ac_011_invalid_reminders_file(box: Sandbox, content: str) -> None:
    """AC-011: every invalid reminders file gives INVALID_REMINDERS and no model call."""
    path = box.write("reminders.json", content)
    run = box.run("--reminders", str(path), REQUEST)
    assert run.error_code(1) == "INVALID_REMINDERS"
    assert box.fake.seen == []


def test_ac_011_missing_reminders_file(box: Sandbox) -> None:
    """AC-011: a reminders file that does not exist gives INVALID_REMINDERS."""
    run = box.run("--reminders", str(box.path("absent.json")), REQUEST)
    assert run.error_code(1) == "INVALID_REMINDERS"
    assert box.fake.seen == []


def test_ac_011_twenty_valid_reminders_are_accepted(box: Sandbox) -> None:
    """AC-011: exactly 20 valid reminders are accepted."""
    box.fake.reply_json(create_reply())
    items = [{**GOOD, "id": f"r{n}"} for n in range(20)]
    path = box.write("reminders.json", json.dumps(items))
    assert box.run("--reminders", str(path), REQUEST).result()["intent"] == "create"


def test_ac_012_missing_key(box: Sandbox) -> None:
    """AC-012: no key anywhere gives MISSING_API_KEY, exit 3, and no model call."""
    run = box.run(REQUEST, env={"GEMINI_API_KEY": None})
    assert run.error_code(3) == "MISSING_API_KEY"
    assert box.fake.seen == []


def test_ac_012_blank_key_counts_as_missing(box: Sandbox) -> None:
    """AC-012: an empty or whitespace key counts as missing."""
    for value in ("", "   "):
        run = box.run(REQUEST, env={"GEMINI_API_KEY": value})
        assert run.error_code(3) == "MISSING_API_KEY"
    assert box.fake.seen == []


def test_ac_013_key_is_read_from_the_env_file(box: Sandbox) -> None:
    """AC-013: comments, blank lines, export and quotes in the .env file are handled."""
    box.fake.reply_json(create_reply())
    text = '# my key\n\n  \nexport GEMINI_API_KEY="file-key-ABCDEFGH1234"\nOTHER=1\n'
    path = box.write("custom.env", text)
    env = {"GEMINI_API_KEY": None, "REMINDER_AGENT_ENV_FILE": str(path)}
    box.run(REQUEST, env=env).result()
    assert box.fake.seen[0].headers["x-goog-api-key"] == "file-key-ABCDEFGH1234"


@pytest.mark.parametrize(
    "line",
    ["GEMINI_API_KEY=plain-key-ABCDEFGH1234", "GEMINI_API_KEY='single-key-ABCDEFGH1234'"],
)
def test_ac_013_other_env_file_forms(box: Sandbox, line: str) -> None:
    """AC-013: unquoted and single-quoted values are read."""
    box.fake.reply_json(create_reply())
    path = box.write("custom.env", line + "\n")
    env = {"GEMINI_API_KEY": None, "REMINDER_AGENT_ENV_FILE": str(path)}
    box.run(REQUEST, env=env).result()
    assert box.fake.seen[0].headers["x-goog-api-key"] == line.split("=", 1)[1].strip("'")


def test_ac_013_environment_wins_over_the_env_file(box: Sandbox) -> None:
    """AC-013: when both exist, the process environment value is used."""
    box.fake.reply_json(create_reply())
    path = box.write("custom.env", "GEMINI_API_KEY=from-file-ABCDEFGH1234\n")
    box.run(REQUEST, env={"REMINDER_AGENT_ENV_FILE": str(path)}).result()
    assert box.fake.seen[0].headers["x-goog-api-key"] == KEY


def test_ac_013_env_file_in_the_working_directory(box: Sandbox) -> None:
    """AC-013: without REMINDER_AGENT_ENV_FILE a .env in the current directory is read."""
    box.fake.reply_json(create_reply())
    box.write(".env", "GEMINI_API_KEY=cwd-key-ABCDEFGH123456\n")
    env = {"GEMINI_API_KEY": None, "REMINDER_AGENT_ENV_FILE": None}
    box.run(REQUEST, env=env).result()
    assert box.fake.seen[0].headers["x-goog-api-key"] == "cwd-key-ABCDEFGH123456"


@pytest.mark.parametrize(
    "base",
    [
        "https://example.com",
        "http://example.com:80",
        "http://127.0.0.1",
        "https://generativelanguage.googleapis.com.evil.example",
        "http://user@127.0.0.1:8080",
        "ftp://127.0.0.1:21",
        "https://127.0.0.1:8443",
        "http://127.0.0.1:8080/prefix",
        "not a url",
    ],
)
def test_ac_024_other_api_bases_are_refused(box: Sandbox, base: str) -> None:
    """AC-024: only the Gemini host (https) or a loopback address (http) is allowed."""
    run = box.run(REQUEST, env={"REMINDER_AGENT_API_BASE": base})
    assert run.error_code(3) == "INVALID_API_BASE"
    assert box.fake.seen == []


@pytest.mark.parametrize(
    "args",
    [
        ["--bogus", "x", REQUEST],
        [],
        ["--model"],
        ["--trace"],
        ["--reminders"],
    ],
)
def test_ac_025_usage_errors(box: Sandbox, args: list[str]) -> None:
    """AC-025: an unknown option, no request, or an option without a value is exit 2."""
    run = box.run(*args)
    assert run.error_code(2) == "USAGE_ERROR"
    assert box.fake.seen == []


def test_ac_025_now_without_a_value(box: Sandbox) -> None:
    """AC-025: --now with no value is a usage error."""
    run = box.run("--now", use_now=False)
    assert run.error_code(2) == "USAGE_ERROR"


def test_ac_025_every_failure_is_one_json_object(box: Sandbox) -> None:
    """AC-025: a failure writes exactly one JSON object on stderr and nothing on stdout."""
    for args in (["--bogus"], [""], ["--model", "bad/name", "x"]):
        run = box.run(*args)
        assert run.out == ""
        assert run.err.count("\n") == 1
        assert list(json.loads(run.err)) == ["error"]


def test_ac_025_a_request_starting_with_a_dash_after_double_dash(box: Sandbox) -> None:
    """AC-025: after -- a request that starts with a dash is accepted (D-9)."""
    box.fake.reply_json(create_reply())
    box.run("--", "-5 minutes from now remind me to stretch").result()
    assert "<request>\n-5 minutes from now remind me to stretch\n</request>" in (
        box.fake.seen[0].user_text()
    )


def test_ac_021_connection_refused_is_unavailable(box: Sandbox) -> None:
    """AC-021: nothing listening on the port gives MODEL_UNAVAILABLE after retries."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    run = box.run(REQUEST, env={"REMINDER_AGENT_API_BASE": f"http://127.0.0.1:{port}"})
    assert run.error_code(3) == "MODEL_UNAVAILABLE"
