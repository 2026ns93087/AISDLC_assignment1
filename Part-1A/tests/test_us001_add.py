"""US-001 Add a task: AC-001, AC-002, AC-004 to AC-013 (FR-001 to FR-007)."""

from support import NOW, Cli, expect_error, expect_ok, make_task, tag_args

EXPECTED_FIRST_TASK = (
    '{"id": 1, "title": "Buy milk", "description": "", "priority": "medium", '
    '"tags": [], "status": "todo", "created_at": "2026-01-01T09:00:00Z", '
    '"updated_at": "2026-01-01T09:00:00Z"}\n'
)


def test_ac_001_add_prints_exact_task_object(cli: Cli) -> None:
    """AC-001: add on an empty store prints exactly the specified object."""
    result = cli.run("add", "--title", "Buy milk")
    assert result.code == 0
    assert result.err == ""
    assert result.out == EXPECTED_FIRST_TASK
    stored = cli.stored()
    assert stored["version"] == 1
    assert stored["next_id"] == 2
    assert stored["tasks"] == [make_task(1, title="Buy milk")]


def test_ac_002_second_task_gets_id_2(cli: Cli) -> None:
    """AC-002: given task 1 exists, the next added task has id 2."""
    cli.seed([make_task(1, title="First")], next_id=2)
    task = expect_ok(cli.run("add", "--title", "Second"))
    assert task["id"] == 2
    assert [t["id"] for t in cli.stored()["tasks"]] == [1, 2]


def test_ac_004_blank_title_is_rejected(cli: Cli) -> None:
    """AC-004: a whitespace-only title fails with TITLE_REQUIRED and changes nothing."""
    result = cli.run("add", "--title", "   ")
    expect_error(result, "TITLE_REQUIRED")
    assert result.after == result.before


def test_ac_005_title_of_100_characters_is_accepted(cli: Cli) -> None:
    """AC-005: a title of exactly 100 characters is stored in full."""
    title = "t" * 100
    task = expect_ok(cli.run("add", "--title", title))
    assert task["title"] == title
    assert len(cli.stored()["tasks"][0]["title"]) == 100


def test_ac_006_title_of_101_characters_is_rejected(cli: Cli) -> None:
    """AC-006: a title of 101 characters fails with TITLE_TOO_LONG and changes nothing."""
    result = cli.run("add", "--title", "t" * 101)
    expect_error(result, "TITLE_TOO_LONG")
    assert result.after == result.before


def test_ac_007_title_is_trimmed(cli: Cli) -> None:
    """AC-007: leading and trailing whitespace is removed from the title."""
    task = expect_ok(cli.run("add", "--title", "  Buy milk  "))
    assert task["title"] == "Buy milk"
    assert cli.stored()["tasks"][0]["title"] == "Buy milk"


def test_ac_008_description_limit_is_500_characters(cli: Cli) -> None:
    """AC-008: 500 characters are accepted, 501 fail with DESCRIPTION_TOO_LONG."""
    accepted = expect_ok(cli.run("add", "--title", "A", "--description", "d" * 500))
    assert accepted["description"] == "d" * 500
    rejected = cli.run("add", "--title", "B", "--description", "d" * 501)
    expect_error(rejected, "DESCRIPTION_TOO_LONG")
    assert rejected.after == rejected.before


def test_ac_009_priority_must_be_low_medium_or_high(cli: Cli) -> None:
    """AC-009: urgent fails with INVALID_PRIORITY, high is accepted and stored."""
    rejected = cli.run("add", "--title", "A", "--priority", "urgent")
    expect_error(rejected, "INVALID_PRIORITY")
    assert rejected.after == rejected.before
    accepted = expect_ok(cli.run("add", "--title", "B", "--priority", "high"))
    assert accepted["priority"] == "high"


def test_ac_010_tags_are_lowercased_deduplicated_and_sorted(cli: Cli) -> None:
    """AC-010: Work, work and home are stored as ["home", "work"]."""
    task = expect_ok(cli.run("add", "--title", "A", *tag_args("Work", "work", "home")))
    assert task["tags"] == ["home", "work"]
    assert cli.stored()["tasks"][0]["tags"] == ["home", "work"]


def test_ac_011_tag_with_invalid_characters_is_rejected(cli: Cli) -> None:
    """AC-011: the tag "bad tag!" fails with INVALID_TAG and changes nothing."""
    result = cli.run("add", "--title", "A", "--tag", "bad tag!")
    expect_error(result, "INVALID_TAG")
    assert result.after == result.before


def test_ac_012_tag_limit_is_20_characters(cli: Cli) -> None:
    """AC-012: a 21-character tag fails with INVALID_TAG, a 20-character tag is accepted."""
    rejected = cli.run("add", "--title", "A", "--tag", "a" * 21)
    expect_error(rejected, "INVALID_TAG")
    assert rejected.after == rejected.before
    accepted = expect_ok(cli.run("add", "--title", "B", "--tag", "a" * 20))
    assert accepted["tags"] == ["a" * 20]


def test_ac_013_at_most_five_distinct_tags(cli: Cli) -> None:
    """AC-013: 5 distinct tags are accepted, 6 fail with TOO_MANY_TAGS."""
    accepted = expect_ok(cli.run("add", "--title", "A", *tag_args("a", "b", "c", "d", "e")))
    assert accepted["tags"] == ["a", "b", "c", "d", "e"]
    rejected = cli.run("add", "--title", "B", *tag_args("a", "b", "c", "d", "e", "f"))
    expect_error(rejected, "TOO_MANY_TAGS")
    assert rejected.after == rejected.before
    assert len(cli.stored()["tasks"]) == 1


def test_ac_001_store_timestamps_use_injected_clock(cli: Cli) -> None:
    """AC-001 (clock): created_at and updated_at equal TODO_NOW, whatever the real time is."""
    task = expect_ok(cli.run("add", "--title", "Clock", now="2030-05-06T07:08:09Z"))
    assert task["created_at"] == "2030-05-06T07:08:09Z"
    assert task["updated_at"] == "2030-05-06T07:08:09Z"
    assert task["created_at"] != NOW
