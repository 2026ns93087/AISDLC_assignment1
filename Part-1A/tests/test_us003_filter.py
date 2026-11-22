"""US-003 Filter tasks: AC-019 to AC-023 (FR-010, FR-011, clarification CL-1)."""

from support import Cli, expect_error, expect_ok, ids, make_task, tag_args


def test_ac_019_filter_by_status(cli: Cli) -> None:
    """AC-019: --status in_progress returns tasks 2 and 3 only, count 2."""
    cli.seed(
        [
            make_task(1, status="todo"),
            make_task(2, status="in_progress"),
            make_task(3, status="in_progress"),
        ],
        next_id=4,
    )
    body = expect_ok(cli.run("list", "--status", "in_progress"))
    assert [task["id"] for task in body["tasks"]] == [2, 3]
    assert body["count"] == 2


def test_ac_020_unknown_status_filter_fails(cli: Cli) -> None:
    """AC-020: --status bogus fails with INVALID_STATUS."""
    cli.seed([make_task(1)], next_id=2)
    expect_error(cli.run("list", "--status", "bogus"), "INVALID_STATUS")


def test_ac_021_filter_by_tag(cli: Cli) -> None:
    """AC-021: --tag work returns task 1 only."""
    cli.seed([make_task(1, tags=("work",)), make_task(2, tags=("home",))], next_id=3)
    assert ids(cli.run("list", *tag_args("work"))) == [1]


def test_ac_022_several_tags_are_combined_with_and(cli: Cli) -> None:
    """AC-022 (CL-1): --tag work --tag home returns only the task carrying both tags."""
    cli.seed([make_task(1, tags=("home", "work")), make_task(2, tags=("work",))], next_id=3)
    body = expect_ok(cli.run("list", *tag_args("work", "home")))
    assert [task["id"] for task in body["tasks"]] == [1]
    assert body["count"] == 1


def test_ac_023_tag_filter_ignores_letter_case(cli: Cli) -> None:
    """AC-023: --tag WORK matches a task tagged work."""
    cli.seed([make_task(1, tags=("work",))], next_id=2)
    assert ids(cli.run("list", *tag_args("WORK"))) == [1]
