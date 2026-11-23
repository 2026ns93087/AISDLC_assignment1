"""US-006: how service failures are handled (FR-014 to FR-016) and the trace file (FR-007).

AC-018 to AC-023. The service is a scripted local fake.
"""

import json

import pytest
from support import KEY, Run, Sandbox, Step, create_reply, gemini_body

REQUEST = "Remind me to call the dentist tomorrow at 3pm"
OK = Step(200, gemini_body(json.dumps(create_reply())))


def error_body(message: str = "oops", code: int = 500) -> bytes:
    return json.dumps({"error": {"code": code, "message": message}}).encode("utf-8")


def test_ac_018_no_candidates(box: Sandbox) -> None:
    """AC-018: a reply with no candidates gives MODEL_EMPTY."""
    box.fake.script(Step(200, json.dumps({"candidates": []}).encode()))
    assert box.run(REQUEST).error_code(3) == "MODEL_EMPTY"
    assert len(box.fake.seen) == 1


def test_ac_018_candidate_without_text(box: Sandbox) -> None:
    """AC-018: a candidate with no text gives MODEL_EMPTY."""
    body = {"candidates": [{"content": {"parts": []}, "finishReason": "STOP"}]}
    box.fake.script(Step(200, json.dumps(body).encode()))
    assert box.run(REQUEST).error_code(3) == "MODEL_EMPTY"


def test_ac_018_prompt_blocked(box: Sandbox) -> None:
    """AC-018: a prompt block reason gives MODEL_BLOCKED."""
    body = {"promptFeedback": {"blockReason": "SAFETY"}}
    box.fake.script(Step(200, json.dumps(body).encode()))
    assert box.run(REQUEST).error_code(3) == "MODEL_BLOCKED"


@pytest.mark.parametrize("finish", ["SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "RECITATION"])
def test_ac_018_safety_finish_reason(box: Sandbox, finish: str) -> None:
    """AC-018: a safety-type finish reason gives MODEL_BLOCKED."""
    box.fake.script(Step(200, gemini_body(json.dumps(create_reply()), finish)))
    assert box.run(REQUEST).error_code(3) == "MODEL_BLOCKED"


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b'"text"', b"null"])
def test_ac_018_reply_that_is_not_a_json_object(box: Sandbox, body: bytes) -> None:
    """AC-018: a 200 reply whose body is not a JSON object gives MODEL_BAD_RESPONSE."""
    box.fake.script(Step(200, body))
    assert box.run(REQUEST).error_code(3) == "MODEL_BAD_RESPONSE"
    assert len(box.fake.seen) == 1


@pytest.mark.parametrize(
    ("status", "message", "code"),
    [
        (401, "unauthorised", "MODEL_AUTH"),
        (403, "forbidden", "MODEL_AUTH"),
        (400, "API key not valid. Please pass a valid API key.", "MODEL_AUTH"),
        (404, "model not found", "MODEL_NOT_FOUND"),
        (400, "Invalid JSON payload", "MODEL_BAD_REQUEST"),
        (422, "unprocessable", "MODEL_BAD_REQUEST"),
    ],
)
def test_ac_019_permanent_errors_are_not_retried(
    box: Sandbox, status: int, message: str, code: str
) -> None:
    """AC-019: auth, not-found and bad-request errors exit 3 after exactly one attempt."""
    box.fake.script(Step(status, error_body(message, status)))
    assert box.run(REQUEST).error_code(3) == code
    assert len(box.fake.seen) == 1


@pytest.mark.parametrize(
    ("status", "code"),
    [(429, "MODEL_RATE_LIMITED"), (503, "MODEL_UNAVAILABLE"), (500, "MODEL_UNAVAILABLE")],
)
def test_ac_020_transient_errors_use_three_attempts(box: Sandbox, status: int, code: str) -> None:
    """AC-020: a transient error on every attempt gives its code after exactly 3 attempts."""
    box.fake.script(Step(status, error_body("busy", status)))
    assert box.run(REQUEST).error_code(3) == code
    assert len(box.fake.seen) == 3


def test_ac_020_recovery_after_one_transient_error(box: Sandbox) -> None:
    """AC-020: a 503 followed by a valid reply gives exit 0 after 2 attempts."""
    box.fake.script(Step(503, error_body("busy", 503)), OK)
    run = box.run(REQUEST)
    assert run.result()["intent"] == "create"
    assert len(box.fake.seen) == 2


def test_ac_020_recovery_on_the_third_attempt(box: Sandbox) -> None:
    """AC-020: two transient errors followed by a valid reply give exit 0 after 3 attempts."""
    box.fake.script(Step(429, error_body("slow", 429)), Step(503, error_body("busy", 503)), OK)
    assert box.run(REQUEST).result()["intent"] == "create"
    assert len(box.fake.seen) == 3


def test_ac_021_slow_reply_times_out(box: Sandbox) -> None:
    """AC-021: a reply slower than the timeout gives MODEL_TIMEOUT after 3 attempts."""
    box.fake.script(Step(200, OK.body, delay=3.0))
    run = box.run(REQUEST, env={"REMINDER_AGENT_TIMEOUT": "1"})
    assert run.error_code(3) == "MODEL_TIMEOUT"
    assert len(box.fake.seen) == 3


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REMINDER_AGENT_TIMEOUT", "abc"),
        ("REMINDER_AGENT_TIMEOUT", "0"),
        ("REMINDER_AGENT_TIMEOUT", "0.5"),
        ("REMINDER_AGENT_TIMEOUT", "601"),
        ("REMINDER_AGENT_TIMEOUT", "nan"),
        ("REMINDER_AGENT_RETRY_DELAY", "abc"),
        ("REMINDER_AGENT_RETRY_DELAY", "-1"),
        ("REMINDER_AGENT_RETRY_DELAY", "61"),
        ("REMINDER_AGENT_RETRY_DELAY", "nan"),
    ],
)
def test_ac_021_invalid_numeric_settings(box: Sandbox, name: str, value: str) -> None:
    """AC-021: a setting that is not a number in range gives INVALID_CONFIG, exit 3."""
    run = box.run(REQUEST, env={name: value})
    assert run.error_code(3) == "INVALID_CONFIG"
    assert box.fake.seen == []


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("REMINDER_AGENT_TIMEOUT", "1"),
        ("REMINDER_AGENT_TIMEOUT", "600"),
        ("REMINDER_AGENT_RETRY_DELAY", "0"),
        ("REMINDER_AGENT_RETRY_DELAY", "0.01"),
    ],
)
def test_ac_021_numeric_settings_at_the_limits_are_accepted(
    box: Sandbox, name: str, value: str
) -> None:
    """AC-021: the lowest and highest allowed values are accepted."""
    box.fake.script(OK)
    assert box.run(REQUEST, env={name: value}).result()["intent"] == "create"


def test_ac_022_trace_after_success(box: Sandbox) -> None:
    """AC-022: the trace has the seven keys, the raw text and no key."""
    box.fake.script(OK)
    trace = box.path("trace.json")
    box.run("--trace", str(trace), REQUEST).result()
    text = trace.read_text(encoding="utf-8")
    document = json.loads(text)
    assert sorted(document) == sorted(
        ["model", "model_version", "finish_reason", "attempts", "usage", "raw_text", "error_code"]
    )
    assert document["model"] == "gemini-flash-latest"
    assert document["model_version"] == "fake-model-1"
    assert document["finish_reason"] == "STOP"
    assert document["attempts"] == 1
    assert document["usage"] == {"promptTokenCount": 11, "totalTokenCount": 22}
    assert json.loads(document["raw_text"]) == create_reply()
    assert document["error_code"] is None
    assert KEY not in text


def test_ac_022_trace_keeps_the_raw_text_when_validation_fails(box: Sandbox) -> None:
    """AC-022: when the output is invalid, the trace still holds the raw text and the code."""
    box.fake.reply_with("I cannot do JSON today")
    trace = box.path("trace.json")
    box.run("--trace", str(trace), REQUEST)
    document = json.loads(trace.read_text(encoding="utf-8"))
    assert document["raw_text"] == "I cannot do JSON today"
    assert document["error_code"] == "MODEL_OUTPUT_INVALID"
    assert document["attempts"] == 1


def test_ac_022_trace_after_an_infrastructure_error(box: Sandbox) -> None:
    """AC-022: after a failed call the trace records the attempts and the error code."""
    box.fake.script(Step(503, error_body("busy", 503)))
    trace = box.path("trace.json")
    box.run("--trace", str(trace), REQUEST)
    document = json.loads(trace.read_text(encoding="utf-8"))
    assert document["error_code"] == "MODEL_UNAVAILABLE"
    assert document["attempts"] == 3
    assert document["raw_text"] is None


def test_ac_022_trace_for_input_errors(box: Sandbox) -> None:
    """AC-022: input errors write a trace with 0 attempts and the error code."""
    trace = box.path("trace.json")
    box.run("--trace", str(trace), "   ")
    document = json.loads(trace.read_text(encoding="utf-8"))
    assert document["attempts"] == 0
    assert document["error_code"] == "EMPTY_REQUEST"


def test_ac_022_trace_that_cannot_be_written(box: Sandbox) -> None:
    """AC-022: an unwritable trace path gives TRACE_WRITE_ERROR, exit 1."""
    box.fake.script(OK)
    run: Run = box.run("--trace", str(box.path("missing-dir") / "t.json"), REQUEST)
    assert run.error_code(1) == "TRACE_WRITE_ERROR"


@pytest.mark.parametrize("status", [401, 400, 500, 404, 429])
def test_ac_023_key_in_an_error_body_never_leaks(box: Sandbox, status: int) -> None:
    """AC-023: an error body that echoes the key never reaches stdout, stderr or the trace."""
    box.fake.script(Step(status, error_body(f"bad credential {KEY} rejected", status)))
    trace = box.path("trace.json")
    run = box.run("--trace", str(trace), REQUEST)
    assert run.code == 3
    assert KEY not in run.out
    assert KEY not in run.err
    assert KEY not in trace.read_text(encoding="utf-8")


def test_ac_023_key_echoed_inside_the_model_text(box: Sandbox) -> None:
    """AC-023: a model text that contains the key does not put the key in the trace or output."""
    box.fake.reply_with(f"the key is {KEY}")
    trace = box.path("trace.json")
    run = box.run("--trace", str(trace), REQUEST)
    assert run.code == 3
    assert KEY not in run.err
    assert KEY not in trace.read_text(encoding="utf-8")


def test_ac_023_key_echoed_inside_a_valid_field(box: Sandbox) -> None:
    """AC-023: a key inside an otherwise valid reply is removed from stdout."""
    box.fake.reply_json({**create_reply(), "title": f"note {KEY}"})
    run = box.run(REQUEST)
    assert KEY not in run.out
    assert KEY not in run.err
