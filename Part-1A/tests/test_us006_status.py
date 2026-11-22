"""US-006 Move a task through statuses: AC-032 to AC-038 (FR-015, clarification CL-3)."""

from support import Cli, expect_error, expect_ok, make_task


def test_ac_032_todo_to_in_progress(cli: Cli) -> None:
    """AC-032: todo to in_progress succeeds."""
    cli.seed([make_task(1, status="todo")], next_id=2)
    task = expect_ok(cli.run("status", "1", "in_progress"))
    assert task["status"] == "in_progress"
    assert cli.stored()["tasks"][0]["status"] == "in_progress"


def test_ac_033_in_progress_to_done_sets_updated_at(cli: Cli) -> None:
    """AC-033: in_progress to done succeeds and updated_at is TODO_NOW."""
    cli.seed([make_task(1, status="in_progress")], next_id=2)
    task = expect_ok(cli.run("status", "1", "done", now="2026-01-03T08:00:00Z"))
    assert task["status"] == "done"
    assert task["updated_at"] == "2026-01-03T08:00:00Z"
    assert task["created_at"] == "2026-01-01T09:00:00Z"


def test_ac_034_todo_to_done_directly(cli: Cli) -> None:
    """AC-034 (CL-3): todo to done succeeds directly."""
    cli.seed([make_task(1, status="todo")], next_id=2)
    task = expect_ok(cli.run("status", "1", "done"))
    assert task["status"] == "done"


def test_ac_035_done_to_todo_reopens(cli: Cli) -> None:
    """AC-035: done to todo succeeds."""
    cli.seed([make_task(1, status="done")], next_id=2)
    task = expect_ok(cli.run("status", "1", "todo"))
    assert task["status"] == "todo"


def test_ac_036_same_status_is_an_invalid_transition(cli: Cli) -> None:
    """AC-036: todo to todo fails with INVALID_TRANSITION and changes nothing."""
    cli.seed([make_task(1, status="todo")], next_id=2)
    result = cli.run("status", "1", "todo")
    expect_error(result, "INVALID_TRANSITION")
    assert result.after == result.before


def test_ac_037_done_to_in_progress_is_not_allowed(cli: Cli) -> None:
    """AC-037: done to in_progress fails with INVALID_TRANSITION and changes nothing."""
    cli.seed([make_task(1, status="done")], next_id=2)
    result = cli.run("status", "1", "in_progress")
    expect_error(result, "INVALID_TRANSITION")
    assert result.after == result.before


def test_ac_038_unknown_status_value(cli: Cli) -> None:
    """AC-038: in_progress to waiting fails with INVALID_STATUS and changes nothing."""
    cli.seed([make_task(1, status="in_progress")], next_id=2)
    result = cli.run("status", "1", "waiting")
    expect_error(result, "INVALID_STATUS")
    assert result.after == result.before
