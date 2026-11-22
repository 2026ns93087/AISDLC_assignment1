# Data Model: Smart Todo CLI

**Date**: 2026-11-22 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Task

Field order below is the JSON key order (AC-001, NFR-005).

| Field | Type | Rule | Source |
|-------|------|------|--------|
| `id` | integer | `>= 1`, unique, never reused | FR-007 |
| `title` | string | trimmed, 1 to 100 characters | FR-002 |
| `description` | string | 0 to 500 characters, default `""` | FR-003 |
| `priority` | string | `low`, `medium`, `high`; default `medium` | FR-004 |
| `tags` | list of string | lower-case, unique, sorted, 0 to 5 items, each 1 to 20 characters of `a-z 0-9 _ -` | FR-005 |
| `status` | string | `todo`, `in_progress`, `done`; new tasks start as `todo` | FR-006, FR-015 |
| `created_at` | string | `YYYY-MM-DDTHH:MM:SSZ`, never changes | FR-006, FR-013 |
| `updated_at` | string | `YYYY-MM-DDTHH:MM:SSZ`, set on edit and status change | FR-013, FR-015 |

## Store (file content)

```json
{
  "version": 1,
  "next_id": 3,
  "tasks": []
}
```

| Field | Type | Rule |
|-------|------|------|
| `version` | integer | must equal 1, otherwise `STORAGE_CORRUPT` (FR-021) |
| `next_id` | integer | the identifier given to the next new task; never decreases (FR-007) |
| `tasks` | list of Task | any order on disk; commands return them by the rules in FR-009 and FR-012 |

A store is corrupt (`STORAGE_CORRUPT`, exit 1, file untouched) when the file is not valid JSON, the
top level is not an object, `version`, `next_id` or `tasks` is missing, `version` is not 1, `next_id`
is not an integer, or `tasks` is not a list. A missing file is an empty store: `version` 1,
`next_id` 1, no tasks (FR-022).

## Status transitions (FR-015, CL-3)

| From | To | Allowed |
|------|----|---------|
| `todo` | `in_progress` | yes |
| `todo` | `done` | yes |
| `in_progress` | `done` | yes |
| `in_progress` | `todo` | yes |
| `done` | `todo` | yes |
| `done` | `in_progress` | no (`INVALID_TRANSITION`) |
| any | same status | no (`INVALID_TRANSITION`) |
| any | other string | no (`INVALID_STATUS`) |

`edit` is refused with `TASK_LOCKED` while `status` is `done` (FR-014, CL-2).

## Error catalogue

| Code | Exit | Raised by |
|------|------|-----------|
| `TITLE_REQUIRED` | 1 | FR-002 |
| `TITLE_TOO_LONG` | 1 | FR-002 |
| `DESCRIPTION_TOO_LONG` | 1 | FR-003 |
| `INVALID_PRIORITY` | 1 | FR-004 |
| `INVALID_TAG` | 1 | FR-005 |
| `TOO_MANY_TAGS` | 1 | FR-005 |
| `TASK_NOT_FOUND` | 1 | FR-008, FR-016 |
| `INVALID_STATUS` | 1 | FR-010, FR-015 |
| `INVALID_SORT` | 1 | FR-012 |
| `TASK_LOCKED` | 1 | FR-014 |
| `INVALID_TRANSITION` | 1 | FR-015 |
| `INVALID_CLOCK` | 1 | FR-020 |
| `STORAGE_CORRUPT` | 1 | FR-021 |
| `INVALID_ID` | 2 | FR-023 |
| `USAGE_ERROR` | 2 | FR-019 (unknown command, missing argument, `edit` with no change option) |
