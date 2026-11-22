---
description: "Task list for Smart Todo CLI"
---

# Tasks: Smart Todo CLI

**Input**: `specs/001-smart-todo-cli/` (spec.md, plan.md, research.md, data-model.md, contracts/cli-contract.md)

**Prerequisites**: spec approved (2026-11-22), plan approved (2026-11-22)

**Tests**: REQUIRED. Constitution III makes every `AC-nnn` verifiable by an automated test.

**Task ID format**: `T-nnn`, as set in constitution principle I. Commits cite the task and the
requirement IDs it serves, for example `T-021 AC-004 : ...`.

## Format: `[ID] [P?] [Owner] [Story] Description (paths) -> covers`

- **[P]**: can run in parallel (different files, no dependency)
- **Owner**: `AGENT` = drafted by the coding agent and reviewed by the student; `HUMAN` = the
  student does it personally (checkpoints, logs, decisions)
- **Story**: `US-001` to `US-008` from the spec
- Paths are relative to `Part-1A/`

## Order of work (differs from the Spec Kit template on purpose)

Harness and tests are written and frozen **before** implementation (constitution Development
Workflow 1 and 2, VII). The order is: Phase 1 setup, Phase 2 tests, Phase 3 harness, Phase 4
human checkpoint and baseline tag, Phase 5 implementation, Phase 6 formal runs and evidence,
Phase 7 documentation and final decision. `/speckit-implement` runs Phase 5 only; Phases 1 to 4
are completed first.

---

## Phase 1: Setup

- [x] T-001 [AGENT] Create `pyproject.toml` with pytest, ruff and bandit configuration exactly as in plan PD-3 and PD-4 (no `ignore`, no `per-file-ignores`, `line-length = 100`, `max-complexity = 10`, `max-statements = 50`, `requires-python = ">=3.11"`) -> NFR-002, NFR-003, NFR-004, constitution IV
- [x] T-002 [AGENT] Verify `pytest`, `ruff` and `bandit` install and run on this machine (Windows ARM64, Python 3.15); if not, pin an interpreter with `uv` as in research R-8 and record the versions -> plan PR-1
- [x] T-003 [P] [AGENT] Extend root `.gitignore` for `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `todo.json`, `demo.json` -> constitution VI, NFR-007

**Checkpoint**: all three tools run and report their versions.

---

## Phase 2: Acceptance tests (written from the specification only)

All tests run the CLI in a subprocess through the helper in T-010 and import nothing from
`src/smart_todo` (plan PD-8). Every test function name starts with `test_ac_NNN` or its docstring
names the AC ID. Assertions are exact (constitution III).

- [x] T-010 [AGENT] Create `tests/conftest.py`: helper `run_cli(args, store, now, env)` returning exit code, stdout, stderr and the store bytes; fixture giving a temp directory and default `TODO_NOW=2026-01-01T09:00:00Z` -> spec AC preamble, PD-8
- [x] T-011 [P] [AGENT] [US-001] `tests/test_us001_add.py` -> AC-001, AC-002, AC-004, AC-005, AC-006, AC-007, AC-008, AC-009, AC-010, AC-011, AC-012, AC-013 (FR-001 to FR-007)
- [x] T-012 [P] [AGENT] [US-002] `tests/test_us002_view.py` -> AC-014, AC-015, AC-016, AC-017, AC-018 (FR-008, FR-009, FR-022, FR-023)
- [x] T-013 [P] [AGENT] [US-003] `tests/test_us003_filter.py` -> AC-019, AC-020, AC-021, AC-022, AC-023 (FR-010, FR-011, CL-1)
- [x] T-014 [P] [AGENT] [US-004] `tests/test_us004_sort.py` -> AC-024, AC-025, AC-026 (FR-012)
- [x] T-015 [P] [AGENT] [US-005] `tests/test_us005_edit.py` -> AC-027, AC-028, AC-029, AC-030, AC-031 (FR-013, FR-014, CL-2)
- [x] T-016 [P] [AGENT] [US-006] `tests/test_us006_status.py` -> AC-032, AC-033, AC-034, AC-035, AC-036, AC-037, AC-038 (FR-015, CL-3)
- [x] T-017 [P] [AGENT] [US-007] `tests/test_us007_delete.py` -> AC-003, AC-039, AC-040 (FR-007, FR-016)
- [x] T-018 [P] [AGENT] [US-008] `tests/test_us008_storage.py` -> AC-041, AC-042, AC-043, AC-044, AC-045, AC-046, AC-047 (FR-017 to FR-021, NFR-005)

**Checkpoint**: against an empty `src/`, every test collects and fails (red). Record the count of
test functions and the 47 AC IDs covered.

---

## Phase 3: Harness (independent of the implementation)

Gates never import `smart_todo`. Each gate returns PASS or FAIL and, on failure, findings of the
form `{code, gate, requirement, expected, observed, stdout, stderr}` (plan, harness design).

- [x] T-020 [AGENT] `.harness/run_harness.py`: run every gate in the fixed order of PD-9, never short-circuit, write `evidence/harness-results/run-N/report.json` plus per-gate stdout and stderr, never overwrite an earlier run, exit 0 only when all gates pass -> constitution VII, Development Workflow 3
- [x] T-021 [P] [AGENT] `.harness/gates/integrity.py`: compare `tests/`, `.harness/`, `pyproject.toml` and `specs/` with tag `baseline-1A-before-implement`; fail with `BASELINE_MISSING` when the tag is absent and `PROTECTED_PATH_CHANGED` on any difference (task-list checkbox ticks excepted) -> constitution VII
- [x] T-022 [P] [AGENT] `.harness/gates/secret_path_scan.py`: fail on key-like strings and on absolute machine paths in tracked files -> NFR-007, constitution VI
- [x] T-023 [P] [AGENT] `.harness/gates/stdlib_imports.py`: parse every file in `src/` with `ast`; fail with `NON_STDLIB_IMPORT` for any import outside `sys.stdlib_module_names` and the local package -> NFR-001
- [x] T-024 [P] [AGENT] `.harness/gates/banned_calls.py`: fail with `BANNED_CALL` for `eval`, `exec`, `pickle`, `os.system`, `shell=True` in `src/`, and with `SUPPRESSION_COMMENT` for `# noqa`, `# nosec`, `# type: ignore` in `src/`, `tests/`, `.harness/` -> constitution IV, VI
- [x] T-025 [P] [AGENT] `.harness/gates/ruff_gate.py`: run `ruff check src tests .harness --no-cache --output-format json`; map each violation to a finding -> NFR-002, NFR-004
- [x] T-026 [P] [AGENT] `.harness/gates/bandit_gate.py`: run `bandit -r src -f json -q`; any result of any severity is a finding -> NFR-003
- [x] T-027 [P] [AGENT] `.harness/gates/tests_gate.py`: run `pytest -p no:cacheprovider --junitxml`; each failing test becomes a finding carrying its AC ID, expected and observed text -> AC-001 to AC-047, SC-001
- [x] T-028 [P] [AGENT] `.harness/gates/traceability.py`: every `AC-001` to `AC-047` in the spec appears in at least one test name or docstring; fail with `AC_WITHOUT_TEST` -> NFR-006, SC-003
- [x] T-029 [AGENT] `.harness/self_check.py` and `.harness/fixtures/`: one deliberately broken input per gate (a lint error, a bandit finding, a banned call, a non-stdlib import, a secret, a missing AC test, a failing test, a modified protected file) plus one good input; print a table showing each gate fails on its fixture and passes on the good input -> plan, "showing every gate can fail"

**Checkpoint**: `self_check.py` shows 8 of 8 broken fixtures rejected and the good input accepted.

---

## Phase 4: Human checkpoint and baseline (student only)

- [ ] T-030 [HUMAN] Review `tests/` and `.harness/` against `spec.md`: every AC row has a test with the exact expected value, no assertion is looser than the spec, no test reads the implementation to decide the expected value
- [ ] T-031 [HUMAN] Run the checkpoint: `self_check.py` passes, the tests collect and fail on empty `src/`, Ruff is clean on `tests` and `.harness`
- [ ] T-032 [HUMAN] Create the annotated tag `baseline-1A-before-implement` on the approved commit, with the number of test functions and the number of AC IDs in the annotation; push it. Any later change to a protected path needs a documented amendment

**Checkpoint**: tag exists on `origin`; the integrity gate passes against it.

---

## Phase 5: Implementation (run by `/speckit-implement`)

Implement only what the spec requires; do not edit `tests/`, `.harness/` or `pyproject.toml`.

- [x] T-040 [AGENT] `src/smart_todo/__init__.py`, `__main__.py` (calls `cli.main()`), `errors.py` with `AppError(code, message, exit_code)` and the error catalogue -> FR-018, FR-019, data-model error catalogue
- [x] T-041 [AGENT] `src/smart_todo/storage.py`: load (missing file = empty store, never creates the file on read), validate shape (`STORAGE_CORRUPT`), atomic save via `mkstemp` + `os.replace`, binary UTF-8 write with `\n`, temp file removed on failure -> FR-017, FR-021, FR-022, R-3, R-4
- [x] T-042 [AGENT] [US-001] `src/smart_todo/domain.py`: validation of title, description, priority, tags and task creation with `next_id` -> FR-002, FR-003, FR-004, FR-005, FR-006, FR-007
- [x] T-043 [AGENT] [US-002] [US-003] [US-004] `domain.py`: lookup by id, status and tag filter (AND, case-insensitive), sort by id or priority -> FR-008, FR-009, FR-010, FR-011, FR-012
- [x] T-044 [AGENT] [US-005] `domain.py`: edit with add/remove tags, `updated_at`, `TASK_LOCKED` on done tasks -> FR-013, FR-014
- [x] T-045 [AGENT] [US-006] `domain.py`: status transition table from data-model with `INVALID_TRANSITION` and `INVALID_STATUS` -> FR-015
- [x] T-046 [AGENT] [US-007] `domain.py`: delete by id that never reuses identifiers -> FR-007, FR-016
- [x] T-047 [AGENT] [US-008] `src/smart_todo/cli.py`: `argparse` subclass with JSON error output and `add_help=False` (PD-1), `--file` before the command (PD-2), string identifiers validated by `[1-9][0-9]*` (PD-7), clock from `TODO_NOW` (PD-6, FR-020), JSON output rules and exit codes (PD-5) -> FR-001, FR-008, FR-009, FR-016, FR-018, FR-019, FR-020, FR-023

**Checkpoint**: `python -m pytest -p no:cacheprovider` runs and shows the implementation's results (informal, not evidence); the first formal harness run is in Phase 6.

---

## Phase 6: Formal runs, repair and evidence

- [x] T-050 [AGENT] Copy `src/` unchanged to `evidence/initial-generation/` **before** the first formal harness run; record the commit hash -> constitution VII
- [x] T-051 [AGENT] Run the harness from the working tree; keep the output as `evidence/harness-results/run-1/` -> SC-001, SC-002, SC-003
- [x] T-052 [AGENT] If any gate fails for a genuine reason: pass the structured findings, unchanged, to the coding agent; repair `src/` only; re-run all gates as the next `run-N`; at most 2 repair attempts, then stop for manual review -> constitution VII. Do not stage a failure. If run-1 passes, record that and skip repair
- [x] T-053 [AGENT] Fresh-clone check: clone the repository to a new folder, run the harness there, keep the output -> constitution Additional Constraints
- [x] T-054 [AGENT] Copy the final `src/` to `evidence/final-generation/` after the last passing run -> constitution VII

---

## Phase 7: Documentation, human review and decision

- [x] T-060 [AGENT] `Part-1A/README.md`: install, run, test and harness commands; setup-environment note (OS, tool versions, Spec Kit 1.4.3, copilot integration, `--system-certs` install workaround); known limitation PD-4 (Bandit scope) -> plan, quickstart
- [x] T-061 [AGENT] Run the quickstart commands by hand and compare with `quickstart.md` -> SC-004
- [ ] T-062 [HUMAN] Write `evidence/harness-log.md` in your own words from the run records (brief section 5.3 lists what it must show)
- [ ] T-063 [HUMAN] Record the final ACCEPT or REJECT decision, known limitations and justification

---

## Dependencies and execution order

| Phase | Depends on | Notes |
|-------|-----------|-------|
| 1 Setup | none | T-002 gates everything that runs a tool |
| 2 Tests | T-001, T-002, T-010 | T-011 to T-018 are independent of each other |
| 3 Harness | T-001, T-002 | T-021 to T-028 are independent; T-020 and T-029 need them |
| 4 Checkpoint | Phases 2 and 3 | HUMAN tasks; blocks Phase 5 |
| 5 Implementation | T-032 | T-040 and T-041 first; T-042 to T-046 share `domain.py` so run in order; T-047 last |
| 6 Runs | Phase 5 | T-050 strictly before T-051 |
| 7 Docs and decision | Phase 6 | T-062 and T-063 are the student's |

## Requirement coverage summary

| Group | Covered by |
|-------|-----------|
| AC-001 to AC-047 | tests T-011 to T-018 (each AC named in exactly one task above); verified by T-028 |
| FR-001 to FR-023 | implementation T-040 to T-047 |
| NFR-001 | T-023; NFR-002 and NFR-004 T-001, T-025; NFR-003 T-026; NFR-005 AC-047 via T-018; NFR-006 T-028; NFR-007 T-022 |
| SC-001 to SC-004 | T-051, T-025 and T-026, T-028, T-061 |

## Notes

- Commit after each task or small group; the message starts with the task and requirement IDs.
- No task may weaken a test, a threshold or a gate. A needed change goes through the specification
  and its change history (constitution I and VII).
- Task checkboxes are the only protected-path change allowed after the baseline.
