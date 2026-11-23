# Part 1B: Natural-Language Reminder Agent

A command-line agent that turns a reminder request written in English into one validated JSON
result. It can create a reminder, reschedule or snooze an existing one, ask a question when
something mandatory is missing, or refuse a request it must not act on. The interpretation is done
by Google Gemini. The program checks everything the model returns before printing it.

- Specification: [specs/001-reminder-agent/spec.md](specs/001-reminder-agent/spec.md) (approved 2026-11-23)
- Constitution: [.specify/memory/constitution.md](.specify/memory/constitution.md)

## Setup (Windows PowerShell; macOS and Linux use the same commands with `source .venv/bin/activate`)

```powershell
cd Part-1B
uv venv .venv --system-certs
uv pip install --python .venv\Scripts\python.exe --system-certs -r requirements-dev.txt
copy .env.example .env      # then put your own key after GEMINI_API_KEY=
```

Python 3.11 or newer. The runtime needs nothing beyond the standard library. The `.env` file is
git-ignored and must never be committed.

## Use

```powershell
$env:PYTHONPATH = "src"
python -m reminder_agent --now 2026-03-10T09:00:00+00:00 "Remind me to call the dentist tomorrow at 3pm"
```

Output is one JSON object with the keys `intent`, `title`, `due_at`, `target_id`,
`snooze_minutes`, `missing`, `message`. To reschedule or snooze, give the existing reminders in a
JSON file with `--reminders FILE`. A request that starts with a dash goes after `--`.
Exit codes: `0` success, `1` invalid input, `2` usage error, `3` model or configuration error.
The full interface is in [contracts/cli-contract.md](specs/001-reminder-agent/contracts/cli-contract.md).

Behind a corporate proxy that replaces TLS certificates, the call can fail with
`MODEL_UNAVAILABLE` and a certificate message. Use the machine's certificate store as for `uv`.

## Test and check

```powershell
.venv\Scripts\python.exe -m pytest -q                    # AC-001 to AC-027, fake model only
.venv\Scripts\python.exe .harness\run_harness.py         # 8 static gates, keeps evidence\gate-runs\run-N
.venv\Scripts\python.exe .harness\self_check.py          # proves each gate rejects a broken input
.venv\Scripts\python.exe .harness\run_eval.py            # REAL model: the evaluation that counts
.venv\Scripts\python.exe .harness\run_eval.py --mode fake   # offline check of the harness itself
```

The tests do not call the real model and take about 2.5 minutes (they wait for timeouts on
purpose). `run_eval.py` in real mode makes one model call per case, about 36, with a pause between
calls, and uses your key and quota. Its verdict is `PASS`, `FAIL` or `INCOMPLETE` (an outage or a
quota stop is never a pass). `--mode fake` results are labelled `fake` and are not evidence.
The gate runner needs the tag `baseline-1B-before-implement` and `git`.

## Layout

| Path | Contents |
|------|----------|
| `src/reminder_agent/` | the program |
| `prompts/system.md` | the system instruction sent to the model |
| `tests/` | acceptance tests with a local fake model |
| `evals/dataset.json` | 40 evaluation cases with ground truth |
| `.harness/` | static gates, the three evaluation layers, the runners |
| `evidence/eval-runs/run-N/` | every real evaluation run, never overwritten |
| `evidence/gate-runs/run-N/` | every static gate run |
