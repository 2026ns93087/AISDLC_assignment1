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
# optional, if the default model is too slow for your key: add the line GEMINI_MODEL=gemini-3.5-flash-lite
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

## Results

The real evaluation uses `gemini-3.5-flash-lite` at temperature 0 with JSON output. Every run is kept.

| Run | Verdict | What happened |
|-----|---------|---------------|
| `evidence/eval-runs/run-1` | FAIL | EV-026 ("Reschedule my dentist reminder"): the model asked the right question but set `target_id`, which a clarify answer must keep null (INV-001, exit 3 `MODEL_OUTPUT_INVALID`). Structure, invariants and guardrails 35/36 and 19/20; semantic score 0.976. Reproduced three times (`repro-EV-026.json`). |
| `evidence/eval-runs/run-2` | PASS | After one rule was added to `prompts/system.md` (a clarify answer keeps `target_id` null). All metrics 1.000, all seven thresholds met, 0 findings. |

Static gates: `evidence/gate-runs/run-1` (before the repair) and `run-2` (after) passed all 8.
The first generation (the code as first committed, `97303af`) is in `evidence/initial-generation/`
and the final state in `evidence/final-generation/`; they differ in `config.py` (the key-pattern fix
found on the first real call) and `prompts/system.md` (the repair).

## Notes and limitations

- Two things were found on the first real use. The accepted key pattern did not allow a dot, which
  current Google keys contain (fixed in `src/reminder_agent/config.py`). The default model in the
  specification, `gemini-flash-latest`, did not answer within the timeout for this key, so
  `GEMINI_MODEL=gemini-3.5-flash-lite` is set in the local `.env`. The specification was not changed.
- The specification, plan, code, tests, dataset and harness were produced in one pass; the baseline tag
  was created afterwards. The tests were written by the same agent that wrote the code, and they are
  independent only in that they were frozen and are run by a separate harness.
- The dataset has 40 cases (36 reach the model). One passing run shows that the thresholds were met
  once; the model's replies vary, so a second run could differ.
- Real runs use your key and your quota (about 36 calls). A free key can hit its daily limit.
