# Feature Specification: Smart Todo CLI

**Feature Directory**: `specs/001-smart-todo-cli`
**Created**: 2026-11-22
**Status**: Clarified and approved by the student on 2026-11-22 (CL-1 to CL-3 resolved)
**Governing document**: `.specify/memory/constitution.md` v1.0.0

**Input**: A command-line task manager for one person. Tasks have a title, an optional description,
a priority, tags and a status. Tasks can be added, listed, filtered by status and tag, sorted by
priority, edited, moved between statuses under fixed rules, and deleted. All data is stored in one
local JSON file.

## Scope

**In scope**: task create/read/update/delete, tag and status filtering, priority sorting, status
transitions, JSON persistence, machine-readable output and exit codes.

**Out of scope**: network or web API, users and authentication, due dates and reminders, recurring
tasks, sub-tasks, multiple lists, concurrent writers, import/export formats other than the store
file, colour or interactive output.

**Interface convention**: the program is invoked as `python -m smart_todo` and is written `todo`
below. Global option `--file PATH` selects the store file (default `todo.json` in the current
directory). Environment variable `TODO_NOW` overrides the clock (see FR-020).

## User Scenarios & Testing *(mandatory)*

### US-001 - Add a task (Priority: P1)

As a user, I want to add a task with a title, optional description, priority and tags, so that I
can capture work I need to do.

**Why this priority**: Nothing else works without tasks existing.

**Independent Test**: Run `todo add --title "Buy milk"` on an empty store and inspect the output
and the store file.

**Covers**: FR-001 to FR-007, FR-017. **Verified by**: AC-001 to AC-013.

### US-002 - View tasks (Priority: P1)

As a user, I want to see one task or the list of all tasks, so that I know what is stored.

**Independent Test**: Add two tasks, then run `todo show 1` and `todo list`.

**Covers**: FR-008, FR-009, FR-022, FR-023. **Verified by**: AC-014 to AC-018.

### US-003 - Filter tasks by status and tag (Priority: P2)

As a user, I want to list only tasks with a given status or tag, so that I can focus.

**Independent Test**: Add tasks with different tags and statuses and run `todo list --tag work`.

**Covers**: FR-010, FR-011. **Verified by**: AC-019 to AC-023.

### US-004 - Sort tasks by priority (Priority: P2)

As a user, I want the list ordered from high to low priority, so that I see urgent work first.

**Independent Test**: Add one task of each priority and run `todo list --sort priority`.

**Covers**: FR-012. **Verified by**: AC-024 to AC-026.

### US-005 - Edit a task (Priority: P2)

As a user, I want to change a task's title, description, priority or tags, so that I can correct
or refine it.

**Independent Test**: Add a task, run `todo edit 1 --title "New"`, then `todo show 1`.

**Covers**: FR-013, FR-014. **Verified by**: AC-027 to AC-031.

### US-006 - Move a task through statuses (Priority: P1)

As a user, I want to start, finish and reopen tasks under fixed rules, so that status always
reflects reality.

**Independent Test**: Add a task, run `todo status 1 in_progress`, then `todo status 1 done`.

**Covers**: FR-015. **Verified by**: AC-032 to AC-038.

### US-007 - Delete a task (Priority: P3)

As a user, I want to delete a task, so that the list stays relevant.

**Independent Test**: Add a task, run `todo delete 1`, then `todo list`.

**Covers**: FR-007, FR-016. **Verified by**: AC-003, AC-039, AC-040.

### US-008 - Trustworthy storage and errors (Priority: P1)

As a user, I want my data kept safely and failures reported clearly, so that I never lose tasks or
guess what went wrong.

**Independent Test**: Corrupt the store file by hand and run `todo list`.

**Covers**: FR-017 to FR-023. **Verified by**: AC-041 to AC-047.

### Edge Cases

- Title made only of whitespace, or exactly at / one over the length limit (AC-004 to AC-007).
- Same tag given twice or in different letter case (AC-010).
- Deleting the highest-numbered task, then adding another: identifiers are never reused (AC-003).
- A failed command must leave the store file byte-for-byte unchanged (AC-004, AC-036, AC-043).
- Store file missing, empty, not JSON, or of an unsupported version (AC-017, AC-043).

## Requirements *(mandatory)*

### Task data model

A task has: `id` (integer), `title` (string), `description` (string), `priority`
(`low` | `medium` | `high`), `tags` (list of strings), `status` (`todo` | `in_progress` | `done`),
`created_at` and `updated_at` (UTC timestamps formatted `YYYY-MM-DDTHH:MM:SSZ`).

### Functional Requirements

- **FR-001**: `todo add` MUST create a task, persist it, and print the created task as one JSON
  object on stdout with exit code 0.
- **FR-002**: The title MUST be trimmed of leading and trailing whitespace and MUST contain 1 to 100
  characters after trimming. Otherwise the command fails with `TITLE_REQUIRED` (empty) or
  `TITLE_TOO_LONG` (over 100).
- **FR-003**: The description is optional, defaults to the empty string, and MUST NOT exceed 500
  characters (`DESCRIPTION_TOO_LONG`).
- **FR-004**: Priority MUST be one of `low`, `medium`, `high`; the default is `medium`. Any other
  value fails with `INVALID_PRIORITY`.
- **FR-005**: Tags are lower-cased, de-duplicated and stored sorted alphabetically. A valid tag has
  1 to 20 characters from `a-z`, `0-9`, `_`, `-` (after lower-casing), otherwise `INVALID_TAG`. A
  task MUST NOT have more than 5 distinct tags (`TOO_MANY_TAGS`).
- **FR-006**: A new task has status `todo`, and `created_at` and `updated_at` equal to the current
  time.
- **FR-007**: Identifiers are integers assigned sequentially from 1. An identifier MUST NOT be
  reused after its task is deleted. The next identifier is persisted in the store.
- **FR-008**: `todo show ID` MUST print the task as one JSON object (exit 0), or fail with
  `TASK_NOT_FOUND` (exit 1) when no task has that identifier.
- **FR-009**: `todo list` MUST print `{"tasks": [...], "count": N}`. Default order is identifier
  ascending.
- **FR-010**: `todo list --status S` MUST return only tasks with status `S`. An unknown status fails
  with `INVALID_STATUS`.
- **FR-011**: `todo list --tag T` (option repeatable) MUST return only tasks matching the given
  tags, comparing case-insensitively. When several `--tag` options are given, a task MUST carry ALL
  of them (AND semantics). (Resolved by CL-1.)
- **FR-012**: `todo list --sort priority` MUST order tasks `high`, `medium`, `low`, with ties broken
  by identifier ascending. `--sort id` is the default. Any other value fails with `INVALID_SORT`.
  Filters (FR-010, FR-011) and sorting MAY be combined; filtering is applied first.
- **FR-013**: `todo edit ID` MUST accept `--title`, `--description`, `--priority`, `--add-tag` and
  `--remove-tag` (the tag options are repeatable), apply the same validation as FR-002 to FR-005,
  set `updated_at` to the current time, and leave `id`, `status` and `created_at` unchanged.
  Removing a tag the task does not have is not an error. Calling `edit` with no change option is a
  usage error.
- **FR-014**: A task whose status is `done` MUST NOT be edited: `todo edit` on it fails with
  `TASK_LOCKED` (exit 1) and the store is unchanged. The task can be edited again after it is
  reopened with `todo status ID todo`. (Resolved by CL-2.)
- **FR-015**: `todo status ID NEW_STATUS` MUST change status only along allowed transitions and set
  `updated_at`. Any other change fails with `INVALID_TRANSITION`. Allowed transitions:
  `todo` to `in_progress`; `todo` to `done`; `in_progress` to `done`; `in_progress` to `todo`;
  `done` to `todo`. (The direct `todo` to `done` transition was added by CL-3.) A transition to
  the current status is always `INVALID_TRANSITION`. An unknown status value fails with
  `INVALID_STATUS`.
- **FR-016**: `todo delete ID` MUST remove the task, persist the change and print
  `{"deleted": ID}`; an unknown identifier fails with `TASK_NOT_FOUND`.
- **FR-017**: Data MUST be stored in a single UTF-8 JSON file of the form
  `{"version": 1, "next_id": N, "tasks": [...]}`. Writes MUST be atomic (temporary file in the same
  directory, then replace) and no temporary file may remain afterwards.
- **FR-018**: Successful commands print JSON only on stdout and nothing on stderr. Failed commands
  print nothing on stdout and exactly one JSON object
  `{"error": {"code": "<CODE>", "message": "<text>"}}` on stderr.
- **FR-019**: Exit codes: `0` success; `1` validation or domain error; `2` usage error (unknown
  command, missing or malformed arguments, identifier that is not a positive integer, `edit` with
  no change option).
- **FR-020**: If environment variable `TODO_NOW` is set it MUST be used as the current time; its
  value MUST match `YYYY-MM-DDTHH:MM:SSZ`, otherwise the command fails with `INVALID_CLOCK`
  (exit 1). If unset, the system UTC time is used, truncated to whole seconds.
- **FR-021**: A store file that is not valid JSON, lacks `version`, `next_id` or `tasks`, or has
  `version` other than 1 MUST cause exit 1 with `STORAGE_CORRUPT`, and the file MUST NOT be
  modified.
- **FR-022**: A missing store file is treated as an empty store. Read-only commands (`list`,
  `show`) MUST NOT create the file.
- **FR-023**: An identifier argument that is not a positive decimal integer (for example `abc`, `0`,
  `-1`, `1.5`) fails with `INVALID_ID` and exit 2.

### Non-Functional Requirements

- **NFR-001**: Runtime code imports only the Python standard library.
- **NFR-002**: `ruff check` reports 0 findings under the configured rule set (constitution IV).
- **NFR-003**: `bandit` reports 0 findings of any severity.
- **NFR-004**: No function exceeds cyclomatic complexity 10; no line exceeds 100 characters.
- **NFR-005**: Identical inputs (arguments, store content, `TODO_NOW`) produce byte-identical
  stdout, stderr and store file on repeated runs.
- **NFR-006**: Every `AC-nnn` is referenced by at least one automated test (checked by a
  traceability gate).
- **NFR-007**: No secret, credential or machine-specific absolute path appears in tracked files.

### Key Entities

- **Task**: as defined in "Task data model".
- **Store**: the JSON document holding `version`, `next_id` and the list of tasks.

## Acceptance Criteria *(mandatory)*

Unless stated, the store starts empty, `TODO_NOW=2026-01-01T09:00:00Z`, and "unchanged" means the
store file is byte-for-byte identical before and after the command.

| ID | Covers | Given / When / Then |
|----|--------|---------------------|
| AC-001 | FR-001, FR-006, FR-007 | Given an empty store, when `todo add --title "Buy milk"`, then exit 0 and stdout is exactly `{"id": 1, "title": "Buy milk", "description": "", "priority": "medium", "tags": [], "status": "todo", "created_at": "2026-01-01T09:00:00Z", "updated_at": "2026-01-01T09:00:00Z"}`. |
| AC-002 | FR-007 | Given task 1 exists, when another task is added, then its `id` is 2. |
| AC-003 | FR-007, FR-016 | Given tasks 1 and 2 exist and task 2 is deleted, when a task is added, then its `id` is 3. |
| AC-004 | FR-002, FR-018 | When `todo add --title "   "`, then exit 1, stdout empty, stderr error code `TITLE_REQUIRED`, store unchanged. |
| AC-005 | FR-002 | When adding a title of exactly 100 characters, then exit 0 and the stored title has 100 characters. |
| AC-006 | FR-002 | When adding a title of 101 characters, then exit 1 with `TITLE_TOO_LONG`, store unchanged. |
| AC-007 | FR-002 | When adding the title `"  Buy milk  "`, then the stored title is `Buy milk`. |
| AC-008 | FR-003 | When adding a description of exactly 500 characters, then exit 0; with 501 characters, exit 1 with `DESCRIPTION_TOO_LONG` and the store unchanged. |
| AC-009 | FR-004 | When adding with `--priority urgent`, then exit 1 with `INVALID_PRIORITY`; with `--priority high`, exit 0 and `priority` is `high`. |
| AC-010 | FR-005 | When adding with `--tag Work --tag work --tag home`, then `tags` is `["home", "work"]`. |
| AC-011 | FR-005 | When adding with `--tag "bad tag!"`, then exit 1 with `INVALID_TAG`, store unchanged. |
| AC-012 | FR-005 | When adding with a 21-character tag, then exit 1 with `INVALID_TAG`; with a 20-character tag, exit 0. |
| AC-013 | FR-005 | When adding with 5 distinct tags, then exit 0; with 6 distinct tags, exit 1 with `TOO_MANY_TAGS`. |
| AC-014 | FR-008 | Given task 1 exists, when `todo show 1`, then exit 0 and stdout is the same JSON object that `add` printed. |
| AC-015 | FR-008 | When `todo show 99` and no task 99 exists, then exit 1 with `TASK_NOT_FOUND`. |
| AC-016 | FR-023, FR-019 | When `todo show abc`, `todo show 0`, `todo show -1` or `todo show 1.5`, then each exits 2 with `INVALID_ID`. |
| AC-017 | FR-009, FR-022 | Given the store file does not exist, when `todo list`, then exit 0, stdout is `{"tasks": [], "count": 0}` and the file still does not exist. |
| AC-018 | FR-009 | Given tasks 1, 2, 3 exist, when `todo list`, then `tasks` are ordered 1, 2, 3 and `count` is 3. |
| AC-019 | FR-010 | Given tasks 1 (`todo`), 2 (`in_progress`), 3 (`in_progress`), when `todo list --status in_progress`, then ids 2 and 3 only, `count` 2. |
| AC-020 | FR-010 | When `todo list --status bogus`, then exit 1 with `INVALID_STATUS`. |
| AC-021 | FR-011 | Given task 1 tagged `work`, task 2 tagged `home`, when `todo list --tag work`, then id 1 only. |
| AC-022 | FR-011 | Given task 1 tagged `home, work` and task 2 tagged `work`, when `todo list --tag work --tag home`, then only id 1 is returned and `count` is 1 (AND semantics, CL-1). |
| AC-023 | FR-011 | Given task 1 tagged `work`, when `todo list --tag WORK`, then id 1 is returned. |
| AC-024 | FR-012 | Given tasks 1 (`low`), 2 (`high`), 3 (`medium`), 4 (`high`), when `todo list --sort priority`, then ids in order 2, 4, 3, 1. |
| AC-025 | FR-012 | When `todo list --sort name`, then exit 1 with `INVALID_SORT`. |
| AC-026 | FR-010, FR-011, FR-012 | Given a mix of tasks, when `todo list --status todo --tag work --sort priority`, then only matching tasks are returned, ordered high to low, ties by id. |
| AC-027 | FR-013 | Given task 1 created at 09:00:00Z, when run with `TODO_NOW=2026-01-02T10:00:00Z` `todo edit 1 --title "New"`, then `title` is `New`, `updated_at` is `2026-01-02T10:00:00Z`, `created_at`, `id` and `status` are unchanged. |
| AC-028 | FR-013, FR-019 | When `todo edit 1` with no change option, then exit 2 and the store is unchanged. |
| AC-029 | FR-013, FR-005 | Given task 1 tagged `home`, when `todo edit 1 --add-tag work --remove-tag home --remove-tag absent`, then exit 0 and `tags` is `["work"]`. |
| AC-030 | FR-013, FR-002 | When `todo edit 1 --title ""`, then exit 1 with `TITLE_REQUIRED`, store unchanged. |
| AC-031 | FR-014 | Given task 1 has status `done`, when `todo edit 1 --title "X"`, then exit 1 with `TASK_LOCKED`, stdout empty, store unchanged (CL-2). After `todo status 1 todo`, the same edit exits 0. |
| AC-032 | FR-015 | Given task 1 `todo`, when `todo status 1 in_progress`, then exit 0 and `status` is `in_progress`. |
| AC-033 | FR-015 | Given task 1 `in_progress`, when run with `TODO_NOW=2026-01-03T08:00:00Z` `todo status 1 done`, then `status` is `done` and `updated_at` is `2026-01-03T08:00:00Z`. |
| AC-034 | FR-015 | Given task 1 `todo`, when `todo status 1 done`, then exit 0 and `status` is `done` (direct transition allowed, CL-3). |
| AC-035 | FR-015 | Given task 1 `done`, when `todo status 1 todo`, then exit 0 and `status` is `todo`. |
| AC-036 | FR-015 | Given task 1 `todo`, when `todo status 1 todo`, then exit 1 with `INVALID_TRANSITION`, store unchanged. |
| AC-037 | FR-015 | Given task 1 `done`, when `todo status 1 in_progress`, then exit 1 with `INVALID_TRANSITION`, store unchanged. |
| AC-038 | FR-015 | Given task 1 `in_progress`, when `todo status 1 waiting`, then exit 1 with `INVALID_STATUS`, store unchanged. |
| AC-039 | FR-016 | Given tasks 1 and 2, when `todo delete 1`, then exit 0, stdout `{"deleted": 1}`, and `todo list` returns only task 2. |
| AC-040 | FR-016 | When `todo delete 99`, then exit 1 with `TASK_NOT_FOUND`, store unchanged. |
| AC-041 | FR-017 | Given `todo add` ran in one process, when `todo list` runs in a new process, then the task is returned. |
| AC-042 | FR-017 | After any successful write, the store file parses as UTF-8 JSON with `version` 1, an integer `next_id` and a `tasks` list, and the directory holds no file other than the store. |
| AC-043 | FR-021 | Given the store file contains `not json`, when `todo list`, then exit 1 with `STORAGE_CORRUPT` and the file is unchanged; the same holds for `{"version": 2, "next_id": 1, "tasks": []}`. |
| AC-044 | FR-018 | For every successful command stderr is empty; for every failed command stdout is empty and stderr is exactly one JSON object with `error.code` and `error.message`. |
| AC-045 | FR-019 | When `todo frobnicate`, or `todo add` with no `--title`, then exit 2. |
| AC-046 | FR-020 | When `TODO_NOW=yesterday` and `todo add --title "x"`, then exit 1 with `INVALID_CLOCK`, store unchanged. |
| AC-047 | NFR-005 | Running the same command twice against identical stores with the same `TODO_NOW` gives byte-identical stdout and store file. |

### Non-functional checks (verified by harness gates, not by AC rows)

NFR-001 import check; NFR-002 Ruff gate; NFR-003 Bandit gate; NFR-004 complexity and line-length
rules in Ruff; NFR-006 traceability gate; NFR-007 secret and absolute-path scan.

## Success Criteria *(mandatory)*

- **SC-001**: 47 of 47 acceptance criteria pass in a formal harness run from a clean clone.
- **SC-002**: Ruff and Bandit each report 0 findings, with no suppression comments in the code.
- **SC-003**: The traceability gate finds a test for 100% of `AC-001` to `AC-047`.
- **SC-004**: A user can add, start and complete a task using only the documented commands, and
  every failure names a stable error code.

## Assumptions

- A single user runs one command at a time; concurrent writers are out of scope.
- The store file fits in memory.
- Python 3.11 or newer is available.
- Output key order is as shown in AC-001 (insertion order of the fields listed in the data model).

## Clarifications

### Session 2026-11-22

| ID | Question | Decision | Affects |
|----|----------|----------|---------|
| CL-1 | Several `--tag` options: AND or OR? | A: a task must carry ALL given tags (AND). | FR-011, AC-022 |
| CL-2 | Can a `done` task be edited? | A: No, `edit` fails with `TASK_LOCKED`; reopen first. | FR-014, AC-031 |
| CL-3 | Is `todo` to `done` allowed directly? | B: Yes, allowed. | FR-015, AC-034 |

All three decisions were made by the student (options and recommendations were presented first).

## Change History

| Date | Change | Reason |
|------|--------|--------|
| 2026-11-22 | Initial draft | First specification before clarification |
| 2026-11-22 | CL-1: FR-011 states AND semantics; AC-022 fixed to return id 1 only | Clarification decision |
| 2026-11-22 | CL-2: FR-014 states `TASK_LOCKED` rule; AC-031 fixed | Clarification decision |
| 2026-11-22 | CL-3: FR-015 allows `todo` to `done`; AC-034 fixed to exit 0 and `done` | Clarification decision |
| 2026-11-22 | Edge-case reference for "failed command leaves store unchanged" changed from AC-034 to AC-036 | AC-034 became a success case after CL-3 |
| 2026-11-22 | Status set to Clarified and approved; [NEEDS CLARIFICATION] markers removed | Student approval |
