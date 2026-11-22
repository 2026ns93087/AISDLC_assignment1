"""US-002 View tasks: AC-014 to AC-018 (FR-008, FR-009, FR-019, FR-022, FR-023)."""

import pytest
from support import Cli, expect_error, expect_ok, ids, make_task


def test_ac_014_show_prints_the_object_that_add_printed(cli: Cli) -> None:
    """AC-014: show 1 prints the same JSON as add printed."""
    added = cli.run("add", "--title", "Buy milk", "--tag", "home")
    shown = cli.run("show", "1")
    assert shown.code == 0
    assert shown.err == ""
    assert shown.out == added.out


def test_ac_015_show_unknown_id_fails(cli: Cli) -> None:
    """AC-015: show 99 with no such task fails with TASK_NOT_FOUND."""
    cli.seed([make_task(1)], next_id=2)
    result = cli.run("show", "99")
    expect_error(result, "TASK_NOT_FOUND")
    assert result.after == result.before


@pytest.mark.parametrize("bad_id", ["abc", "0", "-1", "1.5"])
def test_ac_016_invalid_identifier_exits_2(cli: Cli, bad_id: str) -> None:
    """AC-016: abc, 0, -1 and 1.5 each exit 2 with INVALID_ID."""
    cli.seed([make_task(1)], next_id=2)
    result = cli.run("show", bad_id)
    expect_error(result, "INVALID_ID", exit_code=2)
    assert result.after == result.before


def test_ac_017_list_on_missing_store_is_empty_and_creates_nothing(cli: Cli) -> None:
    """AC-017: list with no store file prints an empty list and does not create the file."""
    assert not cli.store.exists()
    result = cli.run("list")
    assert result.code == 0
    assert result.err == ""
    assert result.out == '{"tasks": [], "count": 0}\n'
    assert not cli.store.exists()


def test_ac_018_list_defaults_to_id_ascending(cli: Cli) -> None:
    """AC-018: tasks 1, 2, 3 are listed in that order and count is 3."""
    cli.seed([make_task(3), make_task(1), make_task(2)], next_id=4)
    body = expect_ok(cli.run("list"))
    assert [task["id"] for task in body["tasks"]] == [1, 2, 3]
    assert body["count"] == 3
    assert ids(cli.run("list")) == [1, 2, 3]
