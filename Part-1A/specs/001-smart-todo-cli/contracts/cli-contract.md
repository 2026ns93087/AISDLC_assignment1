# CLI Contract: Smart Todo

**Date**: 2026-11-22 | **Spec**: [../spec.md](../spec.md)

Invocation: `python -m smart_todo [--file PATH] <command> [options]`

`--file` is accepted before the command only (PD-2). Default store file: `todo.json` in the current
directory. Environment: `TODO_NOW` (optional, `YYYY-MM-DDTHH:MM:SSZ`).

| Command | Arguments and options | Success stdout | FR |
|---------|-----------------------|----------------|----|
| `add` | `--title T` (required), `--description D`, `--priority P`, `--tag X` (repeatable) | the created task object | FR-001 to FR-007 |
| `show` | `ID` | the task object | FR-008 |
| `list` | `--status S`, `--tag X` (repeatable, AND), `--sort id\|priority` | `{"tasks": [...], "count": N}` | FR-009 to FR-012 |
| `edit` | `ID`, at least one of `--title`, `--description`, `--priority`, `--add-tag` (repeatable), `--remove-tag` (repeatable) | the updated task object | FR-013, FR-014 |
| `status` | `ID NEW_STATUS` | the updated task object | FR-015 |
| `delete` | `ID` | `{"deleted": ID}` | FR-016 |

## Output rules (FR-018, FR-019)

| Outcome | Exit | stdout | stderr |
|---------|------|--------|--------|
| success | 0 | one JSON value, then newline | empty |
| validation or domain error | 1 | empty | `{"error": {"code": "<CODE>", "message": "<text>"}}` then newline |
| usage error | 2 | empty | same shape, code `USAGE_ERROR` or `INVALID_ID` |

The `message` text is informational and is not asserted by tests; the `code` is.

## Task object (key order fixed)

`{"id": 1, "title": "Buy milk", "description": "", "priority": "medium", "tags": [], "status": "todo", "created_at": "2026-01-01T09:00:00Z", "updated_at": "2026-01-01T09:00:00Z"}`
