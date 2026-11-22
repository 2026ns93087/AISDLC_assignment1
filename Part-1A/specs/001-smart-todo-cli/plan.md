# Implementation Plan: Smart Todo CLI

**Branch**: n/a (work happens on `main`) | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md)

**Input**: Clarified specification `specs/001-smart-todo-cli/spec.md` (CL-1 to CL-3 resolved)

**Status**: Approved by the student on 2026-11-22 (human review gate passed, PD-1 to PD-9 accepted as written)

## Summary

A single-user command-line task manager, invoked as `python -m smart_todo`, that stores tasks in one
JSON file. The design separates a pure domain layer (validation, filtering, sorting, transitions)
from a thin storage layer (atomic JSON read/write) and a thin CLI layer (argument parsing, JSON
output, exit codes). The clock is injected from the CLI layer (read from `TODO_NOW`) so every
behaviour is deterministic (NFR-005, constitution V).

## Technical Context

**Language/Version**: Python 3.11 or newer (constitution, Additional Constraints)

**Primary Dependencies**: none at runtime (NFR-001). Development only: `pytest`, `ruff`, `bandit`

**Storage**: one UTF-8 JSON file, atomic replace (FR-017)

**Testing**: `pytest`; contract tests run the CLI as a subprocess and assert exact stdout, stderr,
exit code and store bytes

**Target Platform**: any OS with Python 3.11+; developed on Windows ARM64

**Project Type**: single project, CLI

**Performance Goals**: none specified; store fits in memory (spec Assumptions)

**Constraints**: stdlib only; complexity at most 10; line length at most 100; no suppression comments

**Scale/Scope**: one user, one store file, tens of tasks

## Constitution Check

*Gate: passes before Phase 0 and again after Phase 1 design.*

| Principle | How this plan complies |
|-----------|------------------------|
| I. Specification is the source of truth | Every module lists the FR IDs it implements (table below). Tasks will cite IDs. |
| II. Standard library first | `argparse`, `json`, `os`, `tempfile`, `datetime`, `re`, `pathlib`, `dataclasses`. No third-party runtime import. |
| III. Test-first, binary ACs | One or more `test_ac_NNN_*` per AC under `tests/`. Tests spawn the CLI; they import nothing from `src/smart_todo`. |
| IV. Static gates, no suppression | Ruff and Bandit configured in `pyproject.toml` with no ignores. See decision PD-3 and PD-4. |
| V. Deterministic domain | `domain.py` takes `now: str` and returns new state; no clock, no file access. IDs come from the store's `next_id`. |
| VI. Safe persistence | `storage.py` writes with `tempfile.mkstemp` in the store directory then `os.replace`. No `eval`, `exec`, `pickle`, `shell=True`. |
| VII. Protected paths | `tests/`, `.harness/`, `pyproject.toml` tool sections, `specs/` are frozen at the baseline tag. |
| VIII. Simplicity | Five small modules, no framework. |

Post-design re-check: no violations. The Complexity Tracking table stays empty.

## Project Structure

### Documentation (this feature)

```text
specs/001-smart-todo-cli/
├── spec.md
├── plan.md                  # this file
├── research.md              # Phase 0
├── data-model.md            # Phase 1
├── quickstart.md            # Phase 1
├── contracts/
│   └── cli-contract.md      # Phase 1
├── checklists/requirements.md
└── tasks.md                 # created by the tasks step
```

### Source code and harness (under `Part-1A/`)

```text
pyproject.toml               # pytest, ruff, bandit configuration (protected after baseline)
src/smart_todo/
├── __init__.py
├── __main__.py              # calls cli.main()
├── errors.py                # AppError(code, message, exit_code)
├── domain.py                # pure functions: validate, add, edit, transition, filter, sort
├── storage.py               # load/save store, atomic write, STORAGE_CORRUPT checks
└── cli.py                   # argparse (JSON-emitting parser), clock, output, exit codes
tests/
├── conftest.py              # helper that runs the CLI in a subprocess in a temp dir
└── test_ac_*.py             # grouped by user story; every test names its AC ID
.harness/
├── run_harness.py           # runs all gates, writes evidence/harness-results/run-N/
├── gates/                   # lint, security, banned-call scan, stdlib-import scan,
│                            #   tests, traceability, integrity, secret/path scan
├── self_check.py            # runs each gate against deliberately broken fixtures
└── fixtures/                # broken inputs used only by self_check
evidence/
├── initial-generation/
├── final-generation/
├── harness-results/run-N/
└── harness-log.md           # written by the student
```

**Structure Decision**: single project. The CLI is the only interface, so no `api/` or `web/`
folders exist.

### Traceability: module to requirement

| Module | Implements |
|--------|-----------|
| `domain.py` | FR-002 to FR-007, FR-010 to FR-015, FR-023 (identifier parsing helper) |
| `storage.py` | FR-017, FR-021, FR-022, FR-007 (persisted `next_id`) |
| `cli.py` | FR-001, FR-008, FR-009, FR-016, FR-018, FR-019, FR-020, FR-023 |
| `errors.py` | FR-018, FR-019 (error codes and exit codes) |

## Plan Decisions (ADR style, for student review)

| ID | Question | Options considered | Choice | Reason |
|----|----------|--------------------|--------|--------|
| PD-1 | Argument parser | `argparse` subclass; hand-written parser; third-party `click` | `argparse` subclass that overrides `error()` to emit the FR-018 JSON and exit 2, with `add_help=False` | stdlib only (NFR-001). Default argparse prints plain text, which would break FR-018 and AC-044. Help output is out of scope. |
| PD-2 | Where `--file` goes | before the subcommand only; after only; both | Before the subcommand only: `todo --file F add --title X` | Simplest for argparse. The spec says "global option". Tests and harness will use this form. |
| PD-3 | Ruff rule set | defaults; broad `select = ["ALL"]`; a stated set | `E, F, W, I, B, UP, SIM, ANN, C90, PLR0915`, `line-length = 100`, `max-complexity = 10`, `max-statements = 50`, no `ignore`, no `per-file-ignores`. Run on `src tests .harness` only | Matches constitution IV. Explicit paths keep Ruff off the Spec Kit script `.specify/scripts/powershell/markdown_sections.py`. Tests and harness code are type-annotated too. |
| PD-4 | Bandit scope | scan `src` and `tests`; scan `src` only; scan all with skips | Scan `src/` only, zero findings of any severity. The banned-call gate (`eval`, `exec`, `pickle`, `shell=True`, `os.system`) additionally scans `src/` | Bandit flags `assert` (B101) and `subprocess` (B404, B603) in tests and the harness runner. Silencing them would break the no-suppression rule, so those folders are outside Bandit scope and are not shipped code. This is a deliberate, disclosed limitation. |
| PD-5 | JSON text format | `ensure_ascii` true or false; compact or spaced | `json.dumps(obj)` defaults (`", "` and `": "` separators, `ensure_ascii=True`) on stdout and stderr. Store file uses `indent=2` plus a trailing newline | Matches AC-001 exactly, avoids console-encoding problems, and is deterministic (NFR-005). |
| PD-6 | Time source | `datetime.now` inside domain; inject | CLI reads `TODO_NOW` or the system UTC time truncated to seconds and passes `now` into domain functions | Constitution V and FR-020. |
| PD-7 | Identifier parsing | `argparse type=int`; manual | Take the argument as a string and validate with the pattern `[1-9][0-9]*` | `type=int` accepts `+1`, `01`, `1_0` and gives the wrong code for `-1`. Spec FR-023 needs `INVALID_ID` with exit 2. |
| PD-8 | Test style | import `smart_todo` in tests; run as subprocess | Subprocess with `PYTHONPATH=src`, `TODO_NOW` set, working directory a pytest `tmp_path` | Keeps tests independent of the implementation's internals, which is the circular-validation control. |
| PD-9 | Harness gate order | all in parallel; fixed order with early stop | Fixed order: integrity, secret/path scan, stdlib-import scan, banned-call scan, ruff, bandit, tests, traceability. All gates always run; none short-circuits | A full finding list per run gives complete feedback to the coding agent. |

## Harness design summary (detail comes in Phase 4)

| Gate | Checks | Spec link |
|------|--------|-----------|
| integrity | protected paths equal the baseline tag | constitution VII |
| secret/path scan | no keys, no absolute machine paths in tracked files | NFR-007 |
| stdlib-import scan | every import in `src/` is in `sys.stdlib_module_names` or local | NFR-001 |
| banned-call scan | no `eval`, `exec`, `pickle`, `shell=True`, `os.system` in `src/` | constitution VI |
| ruff | `ruff check src tests .harness --no-cache` exits 0 | NFR-002, NFR-004 |
| bandit | `bandit -r src -q` reports zero issues | NFR-003 |
| tests | `pytest -p no:cacheprovider` all pass | AC-001 to AC-047 |
| traceability | every AC ID appears in at least one test name or docstring | NFR-006, SC-003 |

Each gate returns PASS or FAIL and, on failure, one or more findings:
`{code, gate, requirement, expected, observed, stdout, stderr}`.

## Risks

| ID | Risk | Mitigation |
|----|------|------------|
| PR-1 | `ruff` or `bandit` wheels unavailable for Windows ARM64 or Python 3.15 | Verify installation in the first harness task. If missing, pin an interpreter with `uv` (3.13 worked for `specify`) and record it in the README setup note. |
| PR-2 | Windows line endings change store bytes between runs | Open files with `newline="\n"` and encoding `utf-8` when writing, so bytes are identical on every platform. |
| PR-3 | Atomic replace fails on Windows when the target is open elsewhere | Out of scope (single writer); the temp file is removed on any failure. |

## Complexity Tracking

No constitution violations. Table intentionally empty.
