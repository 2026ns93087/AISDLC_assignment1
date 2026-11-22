# Smart Todo CLI Constitution
## Core Principles

### I. Specification Is the Source of Truth
Every behaviour MUST trace to a numbered requirement. User stories use `US-nnn`, functional
requirements `FR-nnn`, acceptance criteria `AC-nnn`, non-functional requirements `NFR-nnn`, and
tasks `T-nnn`. Every commit message MUST begin with at least one of these IDs (format
`<ID> : <message>`). Code that implements no requirement MUST NOT be added. An ambiguity found
after approval MUST be fixed in the upstream artifact (spec, plan or tasks) with a dated entry in
that artifact's change history before the code changes.

### II. Standard Library First
Runtime code MUST use only the Python standard library (zero third-party runtime dependencies).
The only permitted development dependencies are `pytest`, `ruff` and `bandit`. Adding any other
dependency requires an amendment to this constitution.

### III. Test-First With Binary Acceptance Criteria
Each `AC-nnn` MUST be verified by at least one automated test whose name or docstring contains
that ID. Tests assert exact values (exact exit codes, exact strings, exact JSON). Assertions such
as "status is non-zero" or "output is not empty" are forbidden where an exact value is specified.
Tests are derived from the specification, never from the implementation.

### IV. Static Quality Gates Without Suppression
Ruff and Bandit MUST both report zero findings. The use of `# noqa`, `# nosec`, `# type: ignore`,
per-file ignores, or rule deselection to silence a tool is forbidden. Measurable limits enforced
by Ruff: maximum cyclomatic complexity 10 per function (`C901`), maximum line length 100,
maximum 50 statements per function (`PLR0915`). Every public function MUST have a type-annotated
signature.

### V. Deterministic Domain Logic
Domain code MUST NOT read the wall clock, generate random values, or touch the filesystem
directly. The current time and the identifier generator MUST be injected so that every test gives
the same result on every run. Task identifiers are sequential integers starting at 1 and are never
reused after deletion.

### VI. Safe Persistence and Input Handling
Task data is persisted as UTF-8 JSON, written atomically (write to a temporary file in the same
directory, then replace). All user input MUST be validated before it changes state. Code MUST NOT
use `eval`, `exec`, `pickle`, `shell=True`, or construct file paths from task content. No secret,
credential or token may appear in source, tests, evidence or history.

### VII. Protected Paths and Preserved Evidence
After the baseline tag for this part is created, the following paths are protected and MUST NOT be
modified by any contributor, including automated tooling, except through a documented amendment:
`tests/`, `.harness/`, `pyproject.toml` lint/security/test configuration, and the files under
`specs/`. Failing tests MUST NOT be deleted, skipped, weakened or marked expected-failure. The first
generated implementation MUST be copied unchanged to `evidence/initial-generation/` before the
first formal harness run. Every harness run MUST be kept under `evidence/harness-results/run-N/`
and never overwritten. A repair cycle is limited to 2 attempts before a manual review.

### VIII. Simplicity
Prefer the smallest design that satisfies the requirements: one package, a pure domain layer, a
thin storage layer and a thin CLI layer. No framework, no plugin system, no feature that is not
required by an `FR-nnn`.

## Additional Constraints

- Language and tooling: Python 3.11 or newer; `pytest` for tests; `ruff` for lint; `bandit` for
  security analysis.
- Interface: a command-line program only. No network service is in scope.
- Exit codes: `0` success, `1` validation or domain error, `2` usage error (see FR IDs in the spec).
- Formal harness runs MUST disable tool caches and MUST run from a clean clone.

## Development Workflow

1. Order of work: constitution, specification, clarification, plan, human review of the plan,
   tasks, analysis, harness and tests, baseline tag, implementation, harness run, repair, human
   decision.
2. Harness and tests are written before implementation and MUST NOT import implementation
   internals to decide expected values.
3. Each harness run produces a machine-readable report with a stable finding code, the gate or
   test, expected and observed values, the relevant requirement ID, and captured stdout/stderr.
4. After the harness reports PASS, a human records ACCEPT or REJECT with known limitations.
## Governance

This constitution supersedes other practices for this part. Amendments require a written reason,
a version bump (MAJOR for removed or redefined principles, MINOR for added or materially expanded
guidance, PATCH for clarification) and a dated entry in the amendment log below. Every
specification, plan and task review MUST check compliance with the principles above, and any
deviation MUST be justified in the plan's complexity section.

### Amendment Log

- 2026-11-22 : 1.0.0 : Initial ratification.

**Version**: 1.0.0 | **Ratified**: 2026-11-22 | **Last Amended**: 2026-11-22

