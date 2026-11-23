# Implementation Plan: Natural-Language Reminder Agent

**Spec**: [spec.md](spec.md) | **Constitution**: `.specify/memory/constitution.md` v1.0.0
**Status**: DRAFT, written together with the spec. Not yet reviewed by the student (task T-100).

## Summary

A standard-library Python program that sends one request to the Gemini REST API, validates the
reply against the schema and invariants of the spec, and prints it. A separate evaluation harness
runs the program over a dataset and decides acceptance from three validation layers and a fixed
threshold table.

## Technical context

| Item | Choice |
|------|--------|
| Language | Python 3.11 or newer, standard library only at runtime |
| Model access | `http.client` to `generativelanguage.googleapis.com`, key in a header (D-2) |
| Dev tools | pytest, ruff, bandit (pinned in `requirements-dev.txt`) |
| Tests | subprocess runs against a local fake model server, never the real model |
| Evaluation | `.harness/run_eval.py`, real model for evidence, fake model for harness checks |

## Constitution check

| Principle | How the plan complies |
|-----------|-----------------------|
| II stdlib only | `http.client`, `json`, `re`, `datetime`; checked by the stdlib gate |
| III never trust the model | `validate.py` checks every rule before anything is printed |
| IV harness independent | gates and evaluators never import `reminder_agent` |
| V tests and dataset frozen | integrity gate covers `tests`, `.harness`, `evals`, `pyproject.toml` |
| VII determinism | the core never reads the clock; `--now` supplies the reference time |
| IX real model for evidence | fake results go to `.harness/fake-runs/` and are labelled `fake` |
| X quality | ruff and bandit with zero findings, no suppression comments |

## Design decisions

| ID | Decision | Alternative rejected |
|----|----------|----------------------|
| PD-1 | One module per concern: `config`, `client`, `prompt`, `validate`, `reminders`, `timeutil`, `cli` | one large file; harder to test and review |
| PD-2 | Validation returns rule IDs, and the CLI turns them into one error naming all of them | stopping at the first violated rule hides failures from the evaluation |
| PD-3 | Retries only for 429, 500, 502, 503, 504, connection failures and timeouts (FR-015) | retrying everything wastes quota and hides permanent errors |
| PD-4 | Output is written as UTF-8 bytes to `sys.stdout.buffer` | avoids Windows console encoding changes |
| PD-5 | The key is redacted from every outgoing message and trace by exact substring | a pattern could miss a differently shaped key |
| PD-6 | The harness reads thresholds, weights, canary and infrastructure codes from `spec.md` | duplicated numbers drift from the spec |
| PD-7 | Verdict has three values: PASS, FAIL, INCOMPLETE | treating an outage as a failure of the agent would be wrong; treating it as a pass worse |
| PD-8 | The dataset ground truth is computed with Python's calendar, not typed by hand | hand-computed dates can contain slips |
| PD-9 | Static gates (`run_harness.py`) and the evaluation (`run_eval.py`) are separate commands | the gates are fast and offline; the evaluation costs model calls |

## Source layout

```
src/reminder_agent/   __main__, cli, config, client, prompt, validate, reminders, timeutil, errors
prompts/system.md     the system instruction (includes the canary token)
tests/                acceptance tests for AC-001 to AC-027, fake model in support.py
evals/dataset.json    40 cases
.harness/gates/       8 static gates
.harness/evaluators/  layer1, layer2, layer3, metrics, dataset, runner, spec_reader
.harness/run_eval.py  the evaluation entry point
.harness/fake_model.py  oracle used to check the harness offline
evidence/             eval-runs/run-N, gate-runs/run-N, initial and final generation
```

## Risks

| Risk | Mitigation |
|------|------------|
| Free-tier quota stops a run part-way | the verdict is INCOMPLETE, never PASS; `--pause` spaces calls |
| The model changes between runs | each report records the model version the service returned |
| Model output varies between runs | thresholds below 1.0 for semantic metrics (D-7); every run is kept |
| A corporate proxy breaks TLS | `MODEL_UNAVAILABLE` with a message pointing to the README |
