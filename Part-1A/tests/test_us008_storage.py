"""US-008 Trustworthy storage and errors: AC-041 to AC-047 (FR-017 to FR-021, NFR-005)."""

import json
from pathlib import Path

import pytest
from support import Cli, expect_error, expect_ok, make_task


def test_ac_041_data_survives_between_processes(cli: Cli) -> None:
    """AC-041: a task added by one process is listed by a new process."""
    expect_ok(cli.run("add", "--title", "Persist me"))
    body = expect_ok(cli.run("list"))
    assert [task["title"] for task in body["tasks"]] == ["Persist me"]


def test_ac_042_store_file_format_and_no_leftovers(cli: Cli) -> None:
    """AC-042: after writes the store is UTF-8 JSON in the FR-017 form and nothing else remains."""
    expect_ok(cli.run("add", "--title", "Caf\u00e9", "--tag", "home"))
    expect_ok(cli.run("status", "1", "done"))
    raw = cli.store.read_bytes()
    document = json.loads(raw.decode("utf-8"))
    assert set(document) == {"version", "next_id", "tasks"}
    assert document["version"] == 1
    assert isinstance(document["next_id"], int)
    assert isinstance(document["tasks"], list)
    assert document["tasks"][0]["title"] == "Caf\u00e9"
    assert [path.name for path in cli.data_dir.iterdir()] == ["todo.json"]


@pytest.mark.parametrize(
    "content",
    [
        b"not json",
        b"",
        b'{"version": 2, "next_id": 1, "tasks": []}',
        b'{"next_id": 1, "tasks": []}',
        b'{"version": 1, "tasks": []}',
        b'{"version": 1, "next_id": 1}',
        b"[]",
    ],
)
def test_ac_043_corrupt_store_is_reported_and_left_untouched(cli: Cli, content: bytes) -> None:
    """AC-043: invalid JSON, wrong version or a missing field give STORAGE_CORRUPT."""
    cli.write_raw(content)
    result = cli.run("list")
    expect_error(result, "STORAGE_CORRUPT")
    assert result.after == content


def test_ac_043_corrupt_store_is_not_overwritten_by_add(cli: Cli) -> None:
    """AC-043: a write command on a corrupt store fails and leaves the file as it was."""
    cli.write_raw(b"not json")
    result = cli.run("add", "--title", "X")
    expect_error(result, "STORAGE_CORRUPT")
    assert result.after == b"not json"


def test_ac_044_success_and_failure_output_channels(cli: Cli) -> None:
    """AC-044: success has empty stderr; failure has empty stdout and one JSON error object."""
    ok = cli.run("add", "--title", "A")
    assert ok.code == 0
    assert ok.err == ""
    json.loads(ok.out)
    failed = cli.run("show", "99")
    assert failed.code == 1
    assert failed.out == ""
    assert failed.err.endswith("\n")
    assert failed.err.count("\n") == 1
    error = json.loads(failed.err)
    assert list(error) == ["error"]
    assert list(error["error"]) == ["code", "message"]
    assert error["error"]["code"] == "TASK_NOT_FOUND"
    assert isinstance(error["error"]["message"], str)
    assert error["error"]["message"] != ""


def test_ac_045_unknown_command_is_a_usage_error(cli: Cli) -> None:
    """AC-045: an unknown command exits 2 with USAGE_ERROR."""
    result = cli.run("frobnicate")
    expect_error(result, "USAGE_ERROR", exit_code=2)
    assert not cli.store.exists()


def test_ac_045_add_without_title_is_a_usage_error(cli: Cli) -> None:
    """AC-045: add with no --title exits 2 with USAGE_ERROR and changes nothing."""
    cli.seed([make_task(1)], next_id=2)
    result = cli.run("add")
    expect_error(result, "USAGE_ERROR", exit_code=2)
    assert result.after == result.before


@pytest.mark.parametrize("clock", ["yesterday", "2026-01-01 09:00:00", "2026-13-45T99:99:99Z"])
def test_ac_046_invalid_clock_is_rejected(cli: Cli, clock: str) -> None:
    """AC-046: a malformed TODO_NOW fails with INVALID_CLOCK and changes nothing."""
    cli.seed([make_task(1)], next_id=2)
    result = cli.run("add", "--title", "x", now=clock)
    expect_error(result, "INVALID_CLOCK")
    assert result.after == result.before


def test_ac_047_identical_runs_give_identical_bytes(cli: Cli, tmp_path: Path) -> None:
    """AC-047: the same command on identical stores gives identical stdout, stderr and store."""
    seed = [make_task(1, title="One", tags=("a", "b"))]
    other = Cli(tmp_path / "second")
    cli.seed(seed, next_id=2)
    other.seed(seed, next_id=2)
    first = cli.run("add", "--title", "Two", "--priority", "high")
    second = other.run("add", "--title", "Two", "--priority", "high")
    assert first.code == second.code == 0
    assert first.out == second.out
    assert first.err == second.err
    assert first.after == second.after
    again = cli.run("list", "--sort", "priority")
    repeat = cli.run("list", "--sort", "priority")
    assert again.out == repeat.out
    assert again.after == repeat.after
