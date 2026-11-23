# AI-Augmented SDLC, Assignment 1: Spec-Driven Development and Harness Engineering

Student ID 2026NS93087. Course SEZG534 (AI-Augmented Software Development Life Cycle), BITS Pilani.

Two small applications are built from a written specification and checked by a harness that does
not import the generated code. The specification, tests, harness and thresholds are written first
and protected by a Git tag; the implementation is written afterwards by a coding agent and kept
unchanged as evidence before any repair.

| Folder | Application | Kind | Result |
|---|---|---|---|
| `Part-1A/` | Smart Todo CLI: tasks with priority, tags and status, stored in one JSON file | Deterministic | 61 tests pass; 8 gates pass (run 2, and run 3 on a fresh clone) after one genuine failure in run 1 |
| `Part-1B/` | Natural-Language Reminder Agent: turns a sentence into one validated JSON action using Google Gemini | Non-deterministic | Real evaluation: run 1 FAIL (1 case), run 2 PASS (all thresholds met, 0 findings) after one prompt repair |

## Use of AI assistance

This assignment was developed with help from AI. GitHub Copilot and Claude (through Claude Code)
were used as coding agents to draft the Spec Kit artifacts and to write implementation, test and
harness code, under my direction and review. The harness logs and the reflection answers are
written by me from the real evidence, as the assignment requires.

## Process notes (what happened, as it happened)

- Part 1A followed the stages in order: constitution, specification, clarification, plan, tasks,
  analysis, tests, harness, implementation, harness runs. The first generated implementation is
  saved unchanged in `Part-1A/evidence/initial-generation/`.
- Part 1B's specification, plan, code, tests, dataset and harness were produced together in one
  pass. The specification was reviewed and approved afterwards (commit `df37dea`, 2026-11-23) and the
  baseline tag `baseline-1B-before-implement` was created after the implementation existed. From
  that tag on, the specification, tests, harness and dataset are protected and were not changed.
- Two small configuration problems were found on the first real use of Part 1B and fixed in
  `src/`: the accepted API-key pattern did not allow a dot (current Google keys contain one), and the
  default model `gemini-flash-latest` is too slow for this key, so `GEMINI_MODEL` is set locally to
  `gemini-3.5-flash-lite`. The default in the specification was not changed.
- No test, dataset case, threshold or specification line was changed to obtain a PASS.

## Part 1A: Smart Todo CLI

- Specification: 8 user stories, 23 functional requirements, 47 acceptance criteria, 63 tasks.
- Harness: 8 gates (integrity against the baseline tag, secret-path scan, standard-library imports,
  banned calls, Ruff, Bandit, tests, traceability) plus a self-check that proves each gate rejects a
  broken input (11 of 11 rejected).
- Run 1 failed: one suppression comment and two `Any` annotations in the first generation. They were
  repaired in `src/` only, and run 2 passed all 8 gates. Run 3 passed on a fresh clone.
- Details, commands and limitations: [Part-1A/README.md](Part-1A/README.md).

## Part 1B: Natural-Language Reminder Agent

- Model `gemini-3.5-flash-lite`, temperature 0, JSON output, standard-library HTTPS client.
- Specification: 7 user stories, 18 functional requirements, 8 non-functional requirements, 27 acceptance
  criteria, a response schema (SCH), invariants (INV), guardrails (GR) and metrics (MET-001 to MET-009).
- Three layers in one harness: structure, invariants and guardrails, and semantic comparison with
  the ground truth. No model acts as judge.
- Dataset: 40 cases (normal, boundary, ambiguous, missing information, malformed, adversarial);
  36 go to the model and 4 are rejected locally.
- Thresholds, fixed before the first real run: structure, invariants, guardrails and input rejection
  at 100%; intent accuracy, field accuracy and the weighted semantic score at least 0.85 (TH-001 to TH-007).
- Run 1 (`evidence/eval-runs/run-1/`): FAIL. Case EV-026 ("Reschedule my dentist reminder"): the model asked the
  right question but set `target_id`, which a clarify answer must keep empty (INV-001). Semantic score 0.976.
- Repair 1: one rule added to `prompts/system.md`. No other file changed.
- Run 2 (`evidence/eval-runs/run-2/`): PASS. All metrics 1.000, all seven thresholds met, 0 findings.
- Details, commands and limitations: [Part-1B/README.md](Part-1B/README.md).

## Layout

```
Part-1A/  .specify/ .github/   Spec Kit templates, skills and the constitution
          specs/               specification, plan, tasks, analysis, contracts
          src/ tests/          the program and the acceptance tests
          .harness/            gates, runner and self-check
          evidence/            initial and final generation, harness runs, harness log
Part-1B/  .specify/ .github/   Spec Kit templates, skills and the constitution
          specs/               specification, plan, tasks, contract, data model
          src/ prompts/ tests/ the program, the system prompt and the tests
          evals/dataset.json   the 40 evaluation cases
          .harness/            gates, three evaluation layers, runners, fake model
          evidence/            initial and final generation, gate runs, evaluation runs, harness log
```
