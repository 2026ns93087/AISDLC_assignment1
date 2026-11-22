# Part 1A: Smart Todo CLI

A command-line task manager for one person. Tasks have a title, an optional description, a
priority, tags and a status. All data is stored in one local JSON file. The program prints JSON
only and reports every failure as one JSON object with a stable error code.

Specification: [specs/001-smart-todo-cli/spec.md](specs/001-smart-todo-cli/spec.md).
Constitution: [.specify/memory/constitution.md](.specify/memory/constitution.md).

## Setup

Requires Python 3.11 or newer. Runtime code uses only the standard library.

```powershell
cd Part-1A
uv venv .venv --system-certs
uv pip install --python .venv\Scripts\python.exe --system-certs pytest ruff bandit
```

## Run

`--file` goes before the command. The default store is `todo.json` in the current directory.
`TODO_NOW` (format `2026-01-01T09:00:00Z`) overrides the clock.

```powershell
$env:PYTHONPATH = "src"
python -m smart_todo --file demo.json add --title "Buy milk" --priority high --tag home
python -m smart_todo --file demo.json list --sort priority
python -m smart_todo --file demo.json status 1 done
```

| Command | Purpose |
|---------|---------|
| `add --title T [--description D] [--priority P] [--tag X ...]` | create a task |
| `show ID` | print one task |
| `list [--status S] [--tag X ...] [--sort id\|priority]` | list tasks (several tags: all must match) |
| `edit ID [--title T] [--description D] [--priority P] [--add-tag X ...] [--remove-tag X ...]` | change a task that is not `done` |
| `status ID NEW_STATUS` | move a task along an allowed transition |
| `delete ID` | remove a task |

Exit codes: `0` success, `1` validation or domain error, `2` usage error.
The full interface is in [specs/001-smart-todo-cli/contracts/cli-contract.md](specs/001-smart-todo-cli/contracts/cli-contract.md).

## Test and check

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check src tests .harness --no-cache
.venv\Scripts\python.exe -m bandit -r src -q
```

## Harness

```powershell
.venv\Scripts\python.exe .harness\run_harness.py        # all 8 gates, keeps evidence/harness-results/run-N/
.venv\Scripts\python.exe .harness\self_check.py         # proves each gate rejects a broken input
```

The harness needs the tag `baseline-1A-before-implement` (the integrity gate compares protected
paths with it) and `git` (found on `PATH`, in `HARNESS_GIT`, or in the default Git for Windows
folder).

## Evidence

| Folder | Content |
|--------|---------|
| `evidence/initial-generation/` | the first generated `src/`, unchanged |
| `evidence/harness-results/run-N/` | every formal run, never overwritten |
| `evidence/final-generation/` | `src/` after the last passing run |

## Setup environment note

| Item | Value |
|------|-------|
| Operating system | Windows (ARM64), PowerShell |
| Project interpreter | Python 3.13.17 in `.venv` (the machine default is 3.15.2) |
| Tools | pytest 9.2.0, ruff 0.17.6, bandit 1.9.4 |
| Spec Kit | specify-cli 1.4.3, copilot integration, PowerShell scripts |
| Install workaround | `uv tool install specify-cli --python 3.13 --system-certs --no-build-package cryptography` (a source build of `cryptography` failed on ARM64, and the corporate certificate store is needed) |

## Known limitations

- Bandit scans `src/` only. Scanning `tests/` and `.harness/` would flag `assert` and
  `subprocess`, and the constitution forbids silencing a tool, so those folders are outside its
  scope. A separate banned-call gate also covers `src/`.
- The traceability gate shows that an acceptance criterion is named in a test. It cannot show
  that the test asserts anything useful; that is a human review.
- One user, one process at a time. Concurrent writers are out of scope.
