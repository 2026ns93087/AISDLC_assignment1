"""US-005 Edit a task: AC-027 to AC-031 (FR-013, FR-014, FR-019, clarification CL-2)."""

from support import Cli, expect_error, expect_ok, make_task


def test_ac_027_edit_title_sets_updated_at_only(cli: Cli) -> None:
    """AC-027: title changes and updated_at is TODO_NOW; id, status, created_at are kept."""
    cli.seed([make_task(1, title="Old", status="in_progress")], next_id=2)
    task = expect_ok(cli.run("edit", "1", "--title", "New", now="2026-01-02T10:00:00Z"))
    assert task == {
        "id": 1,
        "title": "New",
        "description": "",
        "priority": "medium",
        "tags": [],
        "status": "in_progress",
        "created_at": "2026-01-01T09:00:00Z",
        "updated_at": "2026-01-02T10:00:00Z",
    }
    assert cli.stored()["tasks"] == [task]


def test_ac_028_edit_without_change_option_is_a_usage_error(cli: Cli) -> None:
    """AC-028: edit 1 with nothing to change exits 2 and leaves the store unchanged."""
    cli.seed([make_task(1)], next_id=2)
    result = cli.run("edit", "1")
    expect_error(result, "USAGE_ERROR", exit_code=2)
    assert result.after == result.before


def test_ac_029_add_and_remove_tags(cli: Cli) -> None:
    """AC-029: add work, remove home, remove a tag that is absent: tags become ["work"]."""
    cli.seed([make_task(1, tags=("home",))], next_id=2)
    result = cli.run(
        "edit", "1", "--add-tag", "work", "--remove-tag", "home", "--remove-tag", "absent"
    )
    task = expect_ok(result)
    assert task["tags"] == ["work"]
    assert cli.stored()["tasks"][0]["tags"] == ["work"]


def test_ac_030_edit_with_empty_title_is_rejected(cli: Cli) -> None:
    """AC-030: --title "" fails with TITLE_REQUIRED and changes nothing."""
    cli.seed([make_task(1, title="Keep")], next_id=2)
    result = cli.run("edit", "1", "--title", "")
    expect_error(result, "TITLE_REQUIRED")
    assert result.after == result.before


def test_ac_031_done_task_is_locked_until_reopened(cli: Cli) -> None:
    """AC-031 (CL-2): edit on a done task fails with TASK_LOCKED; after reopening it works."""
    cli.seed([make_task(1, title="Old", status="done")], next_id=2)
    locked = cli.run("edit", "1", "--title", "X")
    expect_error(locked, "TASK_LOCKED")
    assert locked.after == locked.before
    expect_ok(cli.run("status", "1", "todo"))
    edited = expect_ok(cli.run("edit", "1", "--title", "X"))
    assert edited["title"] == "X"
