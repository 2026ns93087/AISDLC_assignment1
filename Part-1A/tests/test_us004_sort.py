"""US-004 Sort tasks by priority: AC-024 to AC-026 (FR-012, with FR-010 and FR-011)."""

from support import Cli, expect_error, expect_ok, make_task, tag_args


def test_ac_024_sort_by_priority_high_first_ties_by_id(cli: Cli) -> None:
    """AC-024: priorities low, high, medium, high are listed as ids 2, 4, 3, 1."""
    cli.seed(
        [
            make_task(1, priority="low"),
            make_task(2, priority="high"),
            make_task(3, priority="medium"),
            make_task(4, priority="high"),
        ],
        next_id=5,
    )
    body = expect_ok(cli.run("list", "--sort", "priority"))
    assert [task["id"] for task in body["tasks"]] == [2, 4, 3, 1]
    assert body["count"] == 4


def test_ac_025_unknown_sort_key_fails(cli: Cli) -> None:
    """AC-025: --sort name fails with INVALID_SORT."""
    cli.seed([make_task(1)], next_id=2)
    expect_error(cli.run("list", "--sort", "name"), "INVALID_SORT")


def test_ac_026_filters_and_sort_combine(cli: Cli) -> None:
    """AC-026: status and tag filters apply first, then priority order with ties by id."""
    cli.seed(
        [
            make_task(1, status="todo", tags=("work",), priority="low"),
            make_task(2, status="todo", tags=("work",), priority="high"),
            make_task(3, status="done", tags=("work",), priority="high"),
            make_task(4, status="todo", tags=("home",), priority="high"),
            make_task(5, status="todo", tags=("work",), priority="medium"),
            make_task(6, status="in_progress", tags=("work",), priority="high"),
            make_task(7, status="todo", tags=("home", "work"), priority="high"),
        ],
        next_id=8,
    )
    result = cli.run(
        "list", "--status", "todo", *tag_args("work"), "--sort", "priority"
    )
    body = expect_ok(result)
    assert [task["id"] for task in body["tasks"]] == [2, 7, 5, 1]
    assert body["count"] == 4
