# Tasks: Natural-Language Reminder Agent

**Input**: `specs/001-reminder-agent/` (spec.md, plan.md, data-model.md, contracts/cli-contract.md)
**Status**: Written after the work was done in one pass. Items marked `[STUDENT]` are NOT done and
need you.

Legend: `[x]` done and checked here, `[ ]` open, `[AGENT]` done by the coding agent,
`[STUDENT]` must be done by you.

## Phase 1: Setup

- [x] T-001 [AGENT] `pyproject.toml`, `requirements-dev.txt`, `.env.example`, `.venv` from the pinned file
- [x] T-002 [AGENT] `.gitignore` entries for `.env`, fake runs and scratch folders (checked: `.env` is ignored and untracked)

## Phase 2: Implementation (checked by tests with the fake model)

- [x] T-010 [AGENT] `timeutil`, `errors`, `config`, `reminders`, `prompt` (FR-002 to FR-005, FR-014, FR-017, FR-018)
- [x] T-011 [AGENT] `client` (FR-015, FR-016)
- [x] T-012 [AGENT] `validate` (FR-006, SCH, INV, GR-004)
- [x] T-013 [AGENT] `cli` (FR-001, FR-007, FR-013)
- [x] T-014 [AGENT] `prompts/system.md`

## Phase 3: Tests (AC-001 to AC-027)

- [x] T-020 [AGENT] `tests/test_us001_results.py` -> AC-001 to AC-007, AC-026, AC-027
- [x] T-021 [AGENT] `tests/test_us006_input.py` -> AC-008 to AC-013, AC-021, AC-024, AC-025
- [x] T-022 [AGENT] `tests/test_us006_output_rules.py` -> AC-014 to AC-017
- [x] T-023 [AGENT] `tests/test_us006_service.py` -> AC-018 to AC-023

## Phase 4: Harness

- [x] T-030 [AGENT] 8 static gates adapted from Part 1A, plus a key-in-file check
- [x] T-031 [AGENT] `evals/dataset.json` (40 cases, expected values computed from the calendar)
- [x] T-032 [AGENT] three layers, metrics, verdict, `run_eval.py`
- [x] T-033 [AGENT] `fake_model.py` with defect injection
- [x] T-034 [AGENT] harness shown to fail: invalid JSON, canary leak, wrong intent, wrong time, outage
- [x] T-035 [AGENT] `self_check.py` (11 broken inputs rejected, 8 gates accept the good project)

## Phase 5: Needs you

- [x] T-100 [STUDENT] Review `spec.md`: decisions D-1 to D-9, clarifications CL-1 to CL-4, thresholds TH-001 to TH-007. Change anything you disagree with BEFORE the first real run.
- [x] T-101 [STUDENT] Commit the work, then create the tag `baseline-1B-before-implement` (the integrity gate needs it).
- [x] T-102 [STUDENT] Run the real evaluation: `python .harness/run_eval.py` (uses your key and quota). Keep every run.
- [x] T-103 [STUDENT] If a run fails: read the findings, fix `src/` or `prompts/system.md` (never the dataset or thresholds), and run again. Keep the failed run as evidence.
- [x] T-104 [STUDENT] Run `python .harness/run_harness.py` after the tag exists; all 8 gates must pass.
- [ ] T-105 [STUDENT] Fresh-clone run on a second folder or machine (SC-005).
