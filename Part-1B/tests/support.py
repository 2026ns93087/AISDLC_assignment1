"""Test support: a controllable fake model server and a runner for the agent program.

Nothing here imports the implementation. Expected values come from the specification (spec.md,
data-model.md and contracts/cli-contract.md). Every test talks to a local fake server and never
to the real model (constitution VII).
"""

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
NOW = "2026-03-10T09:00:00+00:00"
KEY = "test-key-ABCDEFGH12345678"
CANARY = "RA-CANARY-4417"
KEYS = ["intent", "title", "due_at", "target_id", "snooze_minutes", "missing", "message"]
Json = dict[str, Any]


def reply(**fields: object) -> Json:
    """A model result object with the seven keys; unspecified keys are null or empty."""
    base: Json = {
        "intent": "create",
        "title": None,
        "due_at": None,
        "target_id": None,
        "snooze_minutes": None,
        "missing": [],
        "message": None,
    }
    base.update(fields)
    return base


def create_reply() -> Json:
    return reply(title="Call the dentist", due_at="2026-03-11T15:00:00+00:00")


def gemini_body(text: str, finish: str = "STOP") -> bytes:
    """A Gemini `generateContent` 200 body that carries one text candidate."""
    document = {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": finish}],
        "modelVersion": "fake-model-1",
        "usageMetadata": {"promptTokenCount": 11, "totalTokenCount": 22},
    }
    return json.dumps(document).encode("utf-8")


@dataclass
class Step:
    """One scripted answer of the fake server."""

    status: int = 200
    body: bytes = b""
    delay: float = 0.0


@dataclass
class Seen:
    """One request received by the fake server."""

    path: str
    headers: dict[str, str]
    body: bytes

    def json(self) -> Json:
        return json.loads(self.body.decode("utf-8"))

    def user_text(self) -> str:
        return str(self.json()["contents"][0]["parts"][0]["text"])

    def system_text(self) -> str:
        return str(self.json()["systemInstruction"]["parts"][0]["text"])


@dataclass
class FakeModel:
    """A local HTTP server that answers with a script and records what it receives."""

    steps: list[Step] = field(default_factory=list)
    seen: list[Seen] = field(default_factory=list)
    server: ThreadingHTTPServer | None = None

    @property
    def base(self) -> str:
        assert self.server is not None
        return f"http://127.0.0.1:{self.server.server_port}"

    def script(self, *steps: Step) -> None:
        self.steps = list(steps)

    def reply_with(self, text: str, finish: str = "STOP") -> None:
        self.script(Step(200, gemini_body(text, finish)))

    def reply_json(self, document: object) -> None:
        self.reply_with(json.dumps(document))

    def stop(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()


def start_fake() -> FakeModel:
    """Start the fake server on a free loopback port."""
    fake = FakeModel()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length)
            headers = {name.lower(): value for name, value in self.headers.items()}
            fake.seen.append(Seen(self.path, headers, body))
            index = min(len(fake.seen) - 1, len(fake.steps) - 1)
            step = fake.steps[index] if fake.steps else Step(500, b"{}")
            if step.delay:
                threading.Event().wait(step.delay)
            self.send_response(step.status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(step.body)))
            self.end_headers()
            try:
                self.wfile.write(step.body)
            except OSError:
                return

        def log_message(self, format: str, *args: object) -> None:
            return

    fake.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=fake.server.serve_forever, daemon=True).start()
    return fake


@dataclass(frozen=True)
class Run:
    """Outcome of one agent run."""

    code: int
    out: str
    err: str

    def result(self) -> Json:
        """The success object, after checking FR-001 and FR-013 (exit 0, newline, empty stderr)."""
        assert self.code == 0, self.err
        assert self.err == ""
        assert self.out.endswith("\n")
        return json.loads(self.out)

    def error_code(self, exit_code: int) -> str:
        """The error code of a failure, after checking FR-013 (empty stdout, one JSON object)."""
        assert self.code == exit_code, self.err
        assert self.out == ""
        assert self.err.endswith("\n")
        assert self.err.count("\n") == 1
        document = json.loads(self.err)
        assert list(document) == ["error"]
        assert sorted(document["error"]) == ["code", "message"]
        return str(document["error"]["code"])

    def error_message(self) -> str:
        return str(json.loads(self.err)["error"]["message"])


class Sandbox:
    """A temporary working directory, a fake model and a way to run the agent against it."""

    def __init__(self, directory: Path, fake: FakeModel) -> None:
        self.dir = directory
        self.fake = fake
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        return self.dir / name

    def write(self, name: str, content: str) -> Path:
        target = self.path(name)
        target.write_text(content, encoding="utf-8", newline="\n")
        return target

    def environment(self, extra: dict[str, str | None] | None = None) -> dict[str, str]:
        env = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith(("GEMINI", "REMINDER_AGENT"))
        }
        env.update(
            {
                "PYTHONPATH": str(SRC),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONIOENCODING": "utf-8",
                "GEMINI_API_KEY": KEY,
                "REMINDER_AGENT_API_BASE": self.fake.base,
                "REMINDER_AGENT_RETRY_DELAY": "0",
                "REMINDER_AGENT_TIMEOUT": "10",
                "REMINDER_AGENT_ENV_FILE": str(self.path("no-such.env")),
            }
        )
        for name, value in (extra or {}).items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
        return env

    def run(
        self,
        *args: str,
        env: dict[str, str | None] | None = None,
        use_now: bool = True,
    ) -> Run:
        """Run `python -m reminder_agent [--now NOW] <args>` in the sandbox directory."""
        command = [sys.executable, "-m", "reminder_agent"]
        if use_now:
            command += ["--now", NOW]
        command += list(args)
        done = subprocess.run(
            command,
            capture_output=True,
            env=self.environment(env),
            cwd=self.dir,
            timeout=60,
            check=False,
        )
        return Run(
            done.returncode,
            done.stdout.decode("utf-8").replace("\r\n", "\n"),
            done.stderr.decode("utf-8").replace("\r\n", "\n"),
        )


def exactly(document: Json) -> str:
    """The exact stdout text for a result object: `json.dumps` defaults plus a newline."""
    return json.dumps(document) + "\n"
