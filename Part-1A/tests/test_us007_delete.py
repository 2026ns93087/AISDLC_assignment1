"""US-007 Delete a task: AC-003, AC-039, AC-040 (FR-007, FR-016)."""

from support import Cli, expect_error, ids, make_task


def test_ac_003_deleted_identifier_is_not_reused(cli: Cli) -> None:
    """AC-003: with tasks 1 and 2, deleting 2 then adding gives the new task id 3."""
    cli.seed([make_task(1), make_task(2)], next_id=3)
    deleted = cli.run("delete", "2")
    assert deleted.code == 0
    added = cli.run("add", "--title", "Third")
    assert added.code == 0
    assert '"id": 3,' in added.out
    assert [task["id"] for task in cli.stored()["tasks"]] == [1, 3]
    assert cli.stored()["next_id"] == 4


def test_ac_039_delete_removes_the_task(cli: Cli) -> None:
    """AC-039: delete 1 prints {"deleted": 1} and list then returns only task 2."""
    cli.seed([make_task(1), make_task(2)], next_id=3)
    result = cli.run("delete", "1")
    assert result.code == 0
    assert result.err == ""
    assert result.out == '{"deleted": 1}\n'
    assert ids(cli.run("list")) == [2]


def test_ac_040_delete_unknown_id_fails(cli: Cli) -> None:
    """AC-040: delete 99 fails with TASK_NOT_FOUND and changes nothing."""
    cli.seed([make_task(1)], next_id=2)
    result = cli.run("delete", "99")
    expect_error(result, "TASK_NOT_FOUND")
    assert result.after == result.before
