# Cross-Artifact Analysis: Smart Todo CLI

**Date**: 2026-11-22 | **Scope**: constitution v1.0.0, spec.md, plan.md, data-model.md,
contracts/cli-contract.md, tasks.md | **Mode**: read-only (no artifact changed by this analysis)

## Method

Scripted checks plus a manual read of every artifact against the constitution.

| Check | Result |
|-------|--------|
| All 47 AC IDs present once in the spec | PASS |
| Every AC named in exactly one test task (T-011 to T-018) | PASS (47 of 47, no duplicates) |
| Every FR-001 to FR-023 named in an implementation task (T-040 to T-047) | PASS |
| `[NEEDS CLARIFICATION]` markers left in the spec | PASS (0 open) |
| Every NFR mapped to a gate or task | PASS (NFR-001 T-023, NFR-002/004 T-001/T-025, NFR-003 T-026, NFR-005 AC-047, NFR-006 T-028, NFR-007 T-022) |
| Self-check covers every gate (8 gates, 8 broken fixtures) | PASS (T-029) |
| Error codes in data-model match spec | FAIL, see A-2 |
| Commit history follows constitution I | FAIL, see A-1 |

## Findings

| ID | Severity | Location | Finding | Recommendation |
|----|----------|----------|---------|----------------|
| A-1 | CRITICAL | constitution I vs git history | Constitution I says every commit MUST begin with a `US-`, `FR-`, `AC-`, `NFR-` or `T-` ID. Six commits begin with `SETUP-001..003`, `CONST-001`, `CL-1` and `PLAN-001`. They are already pushed. | Amend constitution I to MINOR v1.1.0: allow the process IDs `SETUP`, `CONST`, `PLAN`, `CL` and `DOCS`, and require a requirement or task ID on every commit that changes `src/`, `tests/` or `.harness/`. Do not rewrite pushed history. Needs the student's approval. |
| A-2 | MEDIUM | spec FR-018/FR-019 vs plan, data-model, contract | `USAGE_ERROR` (exit 2) is used in the plan, data model, contract and research but is not defined in the spec. FR-018 requires a code on every failure, and AC-044 and AC-045 do not assert which code a usage error carries. | Add `USAGE_ERROR` to FR-019 and to AC-045 with a change-history entry. Needs the student's approval because the spec is approved. |
| A-3 | MEDIUM | constitution VII vs tasks T-021 and Notes | The constitution freezes `specs/` after the baseline tag. Tasks tick checkboxes in `specs/.../tasks.md` after the baseline, and T-021 excepts "task-list checkbox ticks". The constitution does not allow that exception. | Cover it in the same v1.1.0 amendment: protect `spec.md`, `plan.md`, `data-model.md` and `contracts/`, and exclude `tasks.md` checkbox state. |
| A-4 | MEDIUM | T-028 traceability gate | A test can name an AC in its docstring and assert nothing, so the gate proves the AC is mentioned, not verified. | Keep the gate. T-030 (human review of exact assertions) is the real control. State this limit in the harness log. No artifact change. |
| A-5 | LOW | spec Interface convention vs plan PD-2 | The spec says `--file` is a global option but does not say it goes before the subcommand. The plan fixes that position. | Add one sentence to the spec's interface convention. Optional. |
| A-6 | LOW | research R-2 | `todo show -1` may be taken by argparse as an option. AC-016 requires `INVALID_ID` and exit 2. | Already noted as an open point. The implementation must pass `--` or handle it. The test is the judge. |
| A-7 | LOW | plan PD-4 | Bandit does not scan `tests/` or `.harness/`. | Disclosed limitation. Record it in the README and harness log. |
| A-8 | INFO | tasks.md | Phase order puts tests and harness before implementation, which differs from the Spec Kit template. Intentional (constitution Development Workflow 1 and 2). | None. |

## Resolutions (2026-11-22, student approved the recommendations)

| ID | Resolution |
|----|------------|
| A-1 | Constitution amended to v1.1.0 (principle I). Process IDs allowed for commits outside `src/`, `tests/`, `.harness/`. Pushed history kept. |
| A-2 | FR-019 and AC-045 now name `USAGE_ERROR`. Spec change history updated. |
| A-3 | Constitution v1.1.0 principle VII lists the protected spec files and exempts `tasks.md` checkbox state. |
| A-4 | Accepted. Limit to be stated in the harness log. T-030 is the control. |
| A-5 | Interface convention now says `--file` goes before the command. |
| A-6, A-7, A-8 | Accepted as noted. No artifact change. |

## Counts

Critical 1, High 0, Medium 3, Low 3, Info 1.

## Gate for Phase 3

No harness or test work should start until A-1 to A-3 are decided by the student. A-1 is the only
finding that blocks, because the constitution is the highest authority in these artifacts.
