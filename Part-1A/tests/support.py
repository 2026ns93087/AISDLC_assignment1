"""Test support: runs the Smart Todo CLI as a subprocess and checks its output.

Nothing here imports the implementation. Expected values come from the specification
(spec.md, data-model.md and contracts/cli-contract.md).
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
NOW = "2026-01-01T09:00:00Z"


@dataclass(frozen=True)
class Result:
    """Outcome of one CLI run, with the store bytes before and after (None = no file)."""

    code: int
    out: str
    err: str
    before: bytes | None
    after: bytes | None


class Cli:
    """A CLI sandbox: one store file in its own directory, one separate working directory."""

    def __init__(self, directory: Path) -> None:
        self.data_dir = directory / "data"
        self.work_dir = directory / "work"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.store = self.data_dir / "todo.json"

    def seed(self, tasks: list[dict[str, Any]], next_id: int) -> None:
        """Write a valid store file directly (spec FR-017 format)."""
        doc = {"version": 1, "next_id": next_id, "tasks": tasks}
        self.store.write_bytes((json.dumps(doc, indent=2) + "\n").encode("utf-8"))

    def write_raw(self, content: bytes) -> None:
        self.store.write_bytes(content)

    def stored(self) -> dict[str, Any]:
        return json.loads(self.store.read_bytes().decode("utf-8"))

    def run(self, *args: str, now: str | None = NOW) -> Result:
        """Run `python -m smart_todo --file <store> <args>` and capture everything."""
        before = self.store.read_bytes() if self.store.exists() else None
        env = {key: value for key, value in os.environ.items() if key != "TODO_NOW"}
        env["PYTHONPATH"] = str(SRC)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        if now is not None:
            env["TODO_NOW"] = now
        command = [sys.executable, "-m", "smart_todo", "--file", str(self.store), *args]
        done = subprocess.run(
            command,
            capture_output=True,
            env=env,
            cwd=self.work_dir,
            timeout=60,
            check=False,
        )
        after = self.store.read_bytes() if self.store.exists() else None
        return Result(
            code=done.returncode,
            out=done.stdout.decode("utf-8").replace("\r\n", "\n"),
            err=done.stderr.decode("utf-8").replace("\r\n", "\n"),
            before=before,
            after=after,
        )


def make_task(
    task_id: int,
    *,
    title: str = "Task",
    description: str = "",
    priority: str = "medium",
    tags: tuple[str, ...] = (),
    status: str = "todo",
    created_at: str = NOW,
    updated_at: str | None = None,
) -> dict[str, Any]:
    """A task dictionary in the key order of the data model."""
    return {
        "id": task_id,
        "title": title,
        "description": description,
        "priority": priority,
        "tags": sorted(tags),
        "status": status,
        "created_at": created_at,
        "updated_at": created_at if updated_at is None else updated_at,
    }


def tag_args(*tags: str) -> list[str]:
    """['--tag', t1, '--tag', t2, ...]"""
    return [part for tag in tags for part in ("--tag", tag)]


def expect_ok(result: Result) -> dict[str, Any]:
    """Success per FR-018: exit 0, nothing on stderr, one JSON value and a newline on stdout."""
    assert result.code == 0, result.err
    assert result.err == ""
    assert result.out.endswith("\n")
    return json.loads(result.out)


def expect_error(result: Result, code: str, exit_code: int = 1) -> None:
    """Failure per FR-018 and FR-019: exit code, empty stdout, JSON error object with the code."""
    assert result.code == exit_code, result.err
    assert result.out == ""
    observed = json.loads(result.err)["error"]["code"]
    assert observed == code


def ids(result: Result) -> list[int]:
    """Identifiers of the tasks in a successful `list` result, in the order returned."""
    return [task["id"] for task in expect_ok(result)["tasks"]]
