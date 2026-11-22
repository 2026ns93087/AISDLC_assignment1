"""Pure domain logic: validation, filtering, sorting and status transitions.

Nothing here reads the clock, the environment or the filesystem. The current time arrives as
the argument `now`, and the next identifier lives in the store (FR-007, constitution V).
Every function returns new data and leaves its inputs unchanged.
"""

import copy
import re
from dataclasses import dataclass
from typing import Any

from smart_todo.errors import AppError

Task = dict[str, Any]
Store = dict[str, Any]

MAX_TITLE = 100
MAX_DESCRIPTION = 500
MAX_TAGS = 5
PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in_progress", "done")
SORT_KEYS = ("id", "priority")
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
TRANSITIONS = frozenset(
    {
        ("todo", "in_progress"),
        ("todo", "done"),
        ("in_progress", "done"),
        ("in_progress", "todo"),
        ("done", "todo"),
    }
)
TAG_PATTERN = re.compile(r"[a-z0-9_-]{1,20}")
ID_PATTERN = re.compile(r"[1-9][0-9]*")


@dataclass(frozen=True)
class Edit:
    """The changes requested by `todo edit` (FR-013). None or empty means "not requested"."""

    title: str | None = None
    description: str | None = None
    priority: str | None = None
    add_tags: tuple[str, ...] = ()
    remove_tags: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return (
            self.title is None
            and self.description is None
            and self.priority is None
            and not self.add_tags
            and not self.remove_tags
        )


def empty_store() -> Store:
    """The store used when the file does not exist (FR-022)."""
    return {"version": 1, "next_id": 1, "tasks": []}


def parse_id(text: str) -> int:
    """Turn a command-line identifier into a positive integer (FR-023)."""
    if ID_PATTERN.fullmatch(text) is None:
        raise AppError("INVALID_ID", f"Not a positive integer identifier: {text!r}.", 2)
    return int(text)


def validate_title(raw: str) -> str:
    title = raw.strip()
    if not title:
        raise AppError("TITLE_REQUIRED", "The title must not be empty.")
    if len(title) > MAX_TITLE:
        raise AppError("TITLE_TOO_LONG", f"The title is longer than {MAX_TITLE} characters.")
    return title


def validate_description(text: str) -> str:
    if len(text) > MAX_DESCRIPTION:
        message = f"The description is longer than {MAX_DESCRIPTION} characters."
        raise AppError("DESCRIPTION_TOO_LONG", message)
    return text


def validate_priority(value: str) -> str:
    if value not in PRIORITIES:
        raise AppError("INVALID_PRIORITY", f"Priority must be one of {', '.join(PRIORITIES)}.")
    return value


def check_tag_count(tags: set[str]) -> None:
    if len(tags) > MAX_TAGS:
        raise AppError("TOO_MANY_TAGS", f"A task may have at most {MAX_TAGS} tags.")


def normalize_tags(raw: list[str]) -> list[str]:
    """Lower-case, validate, de-duplicate and sort tags (FR-005)."""
    unique: set[str] = set()
    for tag in raw:
        lowered = tag.lower()
        if TAG_PATTERN.fullmatch(lowered) is None:
            raise AppError("INVALID_TAG", f"Invalid tag: {tag!r}.")
        unique.add(lowered)
    check_tag_count(unique)
    return sorted(unique)


def find_task(store: Store, task_id: int) -> Task:
    for task in store["tasks"]:
        if task["id"] == task_id:
            return task
    raise AppError("TASK_NOT_FOUND", f"No task with id {task_id}.")


def with_tasks(store: Store, tasks: list[Task], next_id: int | None = None) -> Store:
    """A copy of the store holding the given tasks."""
    return {
        "version": store["version"],
        "next_id": store["next_id"] if next_id is None else next_id,
        "tasks": tasks,
    }


def replace_task(store: Store, new_task: Task) -> Store:
    tasks = [
        new_task if task["id"] == new_task["id"] else copy.deepcopy(task)
        for task in store["tasks"]
    ]
    return with_tasks(store, tasks)


def create_task(
    store: Store,
    title: str,
    description: str,
    priority: str,
    tags: list[str],
    now: str,
) -> tuple[Store, Task]:
    """Add a task (FR-001 to FR-007). Returns the new store and the created task."""
    task: Task = {
        "id": store["next_id"],
        "title": validate_title(title),
        "description": validate_description(description),
        "priority": validate_priority(priority),
        "tags": normalize_tags(tags),
        "status": "todo",
        "created_at": now,
        "updated_at": now,
    }
    tasks = [*copy.deepcopy(store["tasks"]), task]
    return with_tasks(store, tasks, store["next_id"] + 1), copy.deepcopy(task)


def list_tasks(store: Store, status: str | None, tags: list[str], sort: str) -> list[Task]:
    """Filter by status and tags (all tags must match), then sort (FR-009 to FR-012)."""
    if status is not None and status not in STATUSES:
        raise AppError("INVALID_STATUS", f"Status must be one of {', '.join(STATUSES)}.")
    if sort not in SORT_KEYS:
        raise AppError("INVALID_SORT", f"Sort must be one of {', '.join(SORT_KEYS)}.")
    wanted = {tag.lower() for tag in tags}
    chosen = [
        copy.deepcopy(task)
        for task in store["tasks"]
        if (status is None or task["status"] == status)
        and wanted <= {tag.lower() for tag in task["tags"]}
    ]
    if sort == "priority":
        chosen.sort(key=lambda task: (PRIORITY_RANK[task["priority"]], task["id"]))
    else:
        chosen.sort(key=lambda task: task["id"])
    return chosen


def merge_tags(current: list[str], add: tuple[str, ...], remove: tuple[str, ...]) -> list[str]:
    added = normalize_tags(list(add))
    removed = {tag.lower() for tag in remove}
    combined = (set(current) - removed) | set(added)
    check_tag_count(combined)
    return sorted(combined)


def edit_task(store: Store, task_id: int, changes: Edit, now: str) -> tuple[Store, Task]:
    """Apply an edit (FR-013, FR-014). A task that is `done` cannot be edited."""
    task = find_task(store, task_id)
    if task["status"] == "done":
        raise AppError("TASK_LOCKED", f"Task {task_id} is done; reopen it before editing.")
    edited = copy.deepcopy(task)
    if changes.title is not None:
        edited["title"] = validate_title(changes.title)
    if changes.description is not None:
        edited["description"] = validate_description(changes.description)
    if changes.priority is not None:
        edited["priority"] = validate_priority(changes.priority)
    if changes.add_tags or changes.remove_tags:
        edited["tags"] = merge_tags(task["tags"], changes.add_tags, changes.remove_tags)
    edited["updated_at"] = now
    return replace_task(store, edited), edited


def change_status(store: Store, task_id: int, new_status: str, now: str) -> tuple[Store, Task]:
    """Move a task along an allowed transition (FR-015)."""
    if new_status not in STATUSES:
        raise AppError("INVALID_STATUS", f"Status must be one of {', '.join(STATUSES)}.")
    task = find_task(store, task_id)
    if (task["status"], new_status) not in TRANSITIONS:
        message = f"Cannot change task {task_id} from {task['status']} to {new_status}."
        raise AppError("INVALID_TRANSITION", message)
    changed = {**copy.deepcopy(task), "status": new_status, "updated_at": now}
    return replace_task(store, changed), changed


def delete_task(store: Store, task_id: int) -> Store:
    """Remove a task. The next identifier is kept, so identifiers are never reused (FR-007)."""
    find_task(store, task_id)
    tasks = [copy.deepcopy(task) for task in store["tasks"] if task["id"] != task_id]
    return with_tasks(store, tasks)
