# Reminder Agent Constitution

## Core Principles

### I. Specification Is the Source of Truth
Every behaviour MUST trace to a numbered requirement. Identifiers: user stories `US-nnn`,
functional requirements `FR-nnn`, acceptance criteria `AC-nnn`, non-functional requirements
`NFR-nnn`, schema rules `SCH-nnn`, invariants `INV-nnn`, guardrails `GR-nnn`, metrics `MET-nnn`,
evaluation cases `EV-nnn`, tasks `T-nnn`. Every commit message MUST begin with at least one ID
(format `<ID> : <message>`). A commit that changes `src/`, `prompts/`, `tests/`, `evals/` or
`.harness/` MUST begin with a `T-`, `AC-`, `FR-`, `NFR-`, `SCH-`, `INV-`, `GR-`, `MET-`, `EV-` or
`US-` ID. Other commits MAY begin with a process ID: `SETUP`, `CONST`, `SPEC`, `PLAN`, `CL`, `DOCS` or
`EVID` (with a number, for example `PLAN-001`). An ambiguity found after approval MUST be fixed in
the upstream artifact with a dated entry in its change history before any code changes.

### II. Standard Library First
Runtime code MUST use only the Python standard library. The model is reached with plain HTTPS
requests to the Gemini REST API; no vendor SDK is allowed. The only permitted development
dependencies are `pytest`, `ruff` and `bandit`, pinned in `requirements-dev.txt`. Calls to the model
use `http.client`, not `urllib.request.urlopen`, so that the security scan needs no suppression. Adding any other
dependency requires an amendment to this constitution.

### III. Behavioural Boundaries Before Behaviour
The output schema, the invariants, the guardrails and the evaluation metrics MUST be written in the
specification before any application code. Wording of model output is free; the schema, the
supported intents, the time representation and the safety rules are not. The model is never trusted:
its output is validated by the application and, independently, by the harness.

### IV. One Harness, Three Independent Layers
A single evaluation harness decides acceptance. Layer 1 (structure), layer 2 (invariants and
guardrails) and layer 3 (semantic quality) are separate code with separate findings. A semantic
score MUST NOT hide or replace a structural or invariant failure. The harness MUST NOT import the
application: it runs the application as a program and judges its output. Harness validators MUST be
written independently of the application's validators. No language model is used as a judge in
this part; semantic quality is scored against ground truth stored in the dataset.

### V. Thresholds Are Fixed Before the Final Evaluation
Metric definitions and acceptance thresholds live in the specification and are read from it by the
harness. They MUST NOT be lowered, and benchmark cases MUST NOT be removed or have their expected
results changed, to obtain a PASS. A legitimate change needs a dated specification amendment with a
reason, made before the next evaluation; all earlier runs are kept.

### VI. Secrets Never Leave the Environment
The API key lives only in the process environment or in a git-ignored `.env` file. It MUST NOT
appear in source, tests, prompts, logs, evidence, reports or history. The key is sent only to the
configured Gemini host (or to a loopback address for tests). Error text is redacted before it is
shown. The harness scans tracked files for key-like strings.

### VII. Deterministic Where It Can Be
The core (prompt building, parsing, validation, scoring, reports) MUST NOT read the wall clock: the
reference time is an argument. Only the command-line layer may read the system clock, and only when
`--now` is not given. Model calls use temperature 0. Everything except the model call MUST be a pure
function of its inputs. Tests of the application use a local fake model server; they never call
the real model.

### VIII. Protected Paths and Preserved Evidence
After the baseline tag for this part is created, these paths MUST NOT be modified except through a
documented amendment: `tests/`, `.harness/`, `evals/`, `pyproject.toml`, `requirements-dev.txt`,
and under `specs/001-reminder-agent/` the files `spec.md`, `plan.md`, `data-model.md` and everything
in `contracts/`. The checkbox state in `tasks.md` is the only change allowed to a file under
`specs/` without an amendment. A repair MAY change `src/` and `prompts/`. The first generated
implementation MUST be copied unchanged to `evidence/initial-generation/` before the first
evaluation of the real model. Every evaluation run MUST be kept under `evidence/eval-runs/run-N/`
and never overwritten. A repair cycle is limited to 2 attempts before a manual review.

### IX. Honest Evidence
Only a run against the real model can be published as evidence. Runs against the local fake model
are for checking the harness and MUST be labelled as such and kept out of `evidence/`. A request
that fails for infrastructure reasons (network, quota, outage) is reported as an infrastructure
error, never counted as a pass and never hidden. A failure is never manufactured for the log.

### X. Simplicity and Static Quality
One package, a pure core, a thin model client and a thin command line. Ruff and Bandit MUST report
zero findings; `# noqa`, `# nosec`, `# type: ignore`, per-file ignores and rule deselection are
forbidden. Maximum cyclomatic complexity 10 (`C901`), line length 100, 50 statements per function
(`PLR0915`). Every function MUST have a type-annotated signature.

## Additional Constraints

- Language and tooling: Python 3.11 or newer; `pytest`, `ruff`, `bandit`.
- Interface: a command-line program only. No server, no database, no user accounts.
- Portability: no platform-specific code; every documented command works on Windows, macOS and
  Linux with only Python, `pip` and `git` installed.
- Exit codes: `0` success, `1` invalid request, `2` usage error, `3` model or infrastructure error.

## Development Workflow

1. Order of work: constitution, specification, clarification, plan, human review of the plan,
   tasks, analysis, harness and tests, baseline tag, implementation evaluated by the harness,
   repair, human decision.
2. Harness and tests are written before the real-model evaluation and MUST NOT depend on the
   application's internals to decide expected values.
3. Each evaluation run writes a machine-readable result with a stable finding code, the layer, the
   case, the expected and observed values and the requirement ID.
4. After the harness reports PASS, a human records ACCEPT or REJECT with known limitations.

## Governance

This constitution supersedes other practices for this part. Amendments require a written reason, a
version bump (MAJOR for removed or redefined principles, MINOR for added or materially expanded
guidance, PATCH for clarification) and a dated entry in the amendment log below. Every
specification, plan and task review MUST check compliance with the principles above.

### Amendment Log

- 2026-11-22 : 1.0.0 : Initial ratification (drafted for student review).

**Version**: 1.0.0 | **Ratified**: 2026-11-22 | **Last Amended**: 2026-11-22
