"""Command-line layer: arguments, clock, pipeline, trace file, JSON output and exit codes."""

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NoReturn, TextIO

from reminder_agent.client import ModelError, ModelReply, generate
from reminder_agent.config import (
    DEFAULT_MODEL,
    build_settings,
    merged_environment,
    process_environment,
    redact,
    validate_model,
)
from reminder_agent.errors import AppError
from reminder_agent.prompt import build_user_message, load_system_prompt
from reminder_agent.reminders import load_reminders
from reminder_agent.timeutil import parse_now
from reminder_agent.validate import validated_result

MAX_REQUEST = 500


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser whose failures become a USAGE_ERROR instead of printed usage text."""

    def error(self, message: str) -> NoReturn:
        raise AppError("USAGE_ERROR", message, 2)


@dataclass
class Trace:
    """What the trace file records (FR-007). Filled in as the pipeline advances."""

    model: str | None = None
    model_version: str | None = None
    finish_reason: str | None = None
    attempts: int = 0
    usage: dict[str, object] | None = None
    raw_text: str | None = None
    error_code: str | None = None
    key: str = ""

    def record_reply(self, reply: ModelReply) -> None:
        self.model_version = reply.model_version
        self.finish_reason = reply.finish_reason
        self.attempts = reply.attempts
        self.usage = reply.usage
        self.raw_text = reply.text

    def record_error(self, error: AppError) -> None:
        self.error_code = error.code
        if isinstance(error, ModelError):
            self.attempts = error.attempts
            self.finish_reason = error.finish_reason or self.finish_reason
            self.model_version = error.model_version or self.model_version

    def as_text(self) -> str:
        document = {
            "model": self.model,
            "model_version": self.model_version,
            "finish_reason": self.finish_reason,
            "attempts": self.attempts,
            "usage": self.usage,
            "raw_text": self.raw_text,
            "error_code": self.error_code,
        }
        return redact(json.dumps(document, indent=2), self.key) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(prog="agent", add_help=False, allow_abbrev=False)
    parser.add_argument("--now")
    parser.add_argument("--reminders")
    parser.add_argument("--model")
    parser.add_argument("--trace")
    parser.add_argument("request", nargs="+")
    return parser


def current_time() -> datetime:
    """The system clock as an aware time with a whole-minute offset (FR-003). CLI layer only."""
    local = datetime.now().astimezone().replace(microsecond=0)
    offset = local.utcoffset() or timedelta(0)
    minutes = int(offset.total_seconds() // 60)
    return local.replace(tzinfo=timezone(timedelta(minutes=minutes)))


def clean_request(words: list[str]) -> str:
    """The request text (FR-002)."""
    text = " ".join(words).strip()
    if not text:
        raise AppError("EMPTY_REQUEST", "The request is empty.")
    if len(text) > MAX_REQUEST:
        raise AppError("REQUEST_TOO_LONG", f"The request is longer than {MAX_REQUEST} characters.")
    return text


def pipeline(
    args: argparse.Namespace, environ: Mapping[str, str], cwd: Path, trace: Trace
) -> dict[str, object]:
    """Run one request. Inputs are checked in the order of FR-003 (spec), model call last."""
    request = clean_request(args.request)
    now = parse_now(args.now) if args.now is not None else current_time()
    reminders = load_reminders(args.reminders)
    merged = merged_environment(environ, cwd)
    model = validate_model(args.model or merged.get("GEMINI_MODEL") or DEFAULT_MODEL)
    trace.model = model
    settings = build_settings(merged, model)
    trace.key = settings.api_key
    reply = generate(settings, load_system_prompt(), build_user_message(now, reminders, request))
    trace.record_reply(reply)
    return validated_result(reply.text, now, {item["id"] for item in reminders})


def write_trace(path: str, trace: Trace) -> None:
    """Write the trace file (FR-007)."""
    try:
        Path(path).write_bytes(trace.as_text().encode("utf-8"))
    except OSError as error:
        raise AppError("TRACE_WRITE_ERROR", "The trace file cannot be written.") from error


def emit(stream: TextIO, value: object, key: str = "") -> None:
    """Write one JSON value and a newline as UTF-8 bytes, with the key removed."""
    data = redact(json.dumps(value), key) + "\n"
    stream.buffer.write(data.encode("utf-8"))
    stream.buffer.flush()


def run(argv: list[str], environ: Mapping[str, str], cwd: Path) -> tuple[int, object, str]:
    """Outcome of one invocation: exit code, JSON value for stdout or stderr, and the key."""
    trace = Trace()
    try:
        args = build_parser().parse_args(argv)
    except AppError as error:
        return error.exit_code, {"error": {"code": error.code, "message": error.message}}, ""
    try:
        result: object = pipeline(args, environ, cwd, trace)
        code = 0
    except AppError as error:
        trace.record_error(error)
        failure = {"error": {"code": error.code, "message": error.message}}
        result, code = failure, error.exit_code
    if args.trace is not None:
        try:
            write_trace(args.trace, trace)
        except AppError as error:
            failure = {"error": {"code": error.code, "message": error.message}}
            result, code = failure, error.exit_code
    return code, result, trace.key


def main(argv: list[str] | None = None) -> int:
    code, value, key = run(
        sys.argv[1:] if argv is None else argv, process_environment(), Path.cwd()
    )
    emit(sys.stdout if code == 0 else sys.stderr, value, key)
    return code
