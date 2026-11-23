# Data Model: Natural-Language Reminder Agent

Source: `spec.md` (FR, SCH, INV, GR, MET). This file adds the exact shapes used by the program, the
dataset and the evidence files.

## Result (stdout of a successful run)

One JSON object, keys in this order, printed with `json.dumps` defaults and a trailing newline.

| Key | Type | Rule |
|-----|------|------|
| `intent` | string | SCH-003: `create`, `reschedule`, `snooze`, `clarify`, `unsupported` |
| `title` | string or null | SCH-004 |
| `due_at` | string or null | SCH-005: `YYYY-MM-DDTHH:MM:SS+HH:MM` |
| `target_id` | string or null | SCH-006 |
| `snooze_minutes` | integer or null | SCH-007: 1 to 1440 |
| `missing` | array of string | SCH-008: distinct values of `title`, `time`, `target` |
| `message` | string or null | SCH-009 |

Which fields are set for each intent: spec INV-001.

## Reminder (input file element)

| Key | Type | Rule |
|-----|------|------|
| `id` | string | 1 to 20 characters of `A-Za-z0-9_-`, unique in the array |
| `title` | string | 1 to 100 characters |
| `due_at` | string | same format as `--now` |

The file is a JSON array of at most 20 such objects. Exactly these three keys, no others.

## Error object (stderr of a failed run)

`{"error": {"code": "<CODE>", "message": "<text>"}}`, one line.

## Trace file (`--trace FILE`)

| Key | Type |
|-----|------|
| `model` | string or null (requested model name) |
| `model_version` | string or null (as reported by the service) |
| `finish_reason` | string or null |
| `attempts` | integer (0 when no request was sent) |
| `usage` | object or null (token counts as reported) |
| `raw_text` | string or null (model text before validation; key redacted) |
| `error_code` | string or null |

## Evaluation case (`evals/dataset.json`)

The file is `{"version": 1, "cases": [...]}`.

| Key | Type | Required | Meaning |
|-----|------|----------|---------|
| `id` | string | yes | `EV-nnn`, unique |
| `category` | string | yes | `normal`, `boundary`, `ambiguous`, `missing_info`, `malformed`, `adversarial` |
| `covers` | array of string | yes | spec IDs this case exercises; each must exist in `spec.md` |
| `request` | string | yes | the request text (passed as one argument) |
| `now` | string | yes | reference time passed to `--now` |
| `reminders` | array | no | written as the reminders file (default none) |
| `reminders_raw` | string | no | written verbatim as the reminders file instead (for malformed input) |
| `expect_error` | object | no | `{"exit_code": n, "code": "..."}`; the case is then scored by MET-009 only |
| `intent_in` | array of string | scored cases | acceptable intents |
| `expected_due_at` | string | no | exact `due_at` required |
| `expected_snooze_minutes` | integer | no | exact value required |
| `expected_target_id` | string | no | exact value required |
| `title_keywords` | array of string | no | groups; `a|b` means either word satisfies the group |
| `expected_missing` | array of string | when `intent_in` is `["clarify"]` | exact set of missing parts |
| `message_terms_any` | array of string | when `intent_in` is `["clarify"]` | at least one must appear in `message` |
| `properties` | array of string | no | `must_clarify`, `must_refuse`, `no_canary`, `no_invented_target` |
| `rationale` | string | yes | why the case exists and what makes the expectation right |

## Evaluation result (`evidence/eval-runs/run-N/eval-results.json`)

| Key | Content |
|-----|---------|
| `run`, `timestamp_utc`, `mode` | run number, time, `real` or `fake` |
| `model` | requested name, versions reported by the service, temperature, API host |
| `inputs` | SHA-256 of `dataset.json`, `prompts/system.md` and the thresholds table |
| `git` | commit and whether the tree was clean |
| `cases` | one record per case: outcome, exit code, parsed output, layer 1, 2, 3 findings, trace summary |
| `metrics` | MET-001 to MET-009, each with numerator, denominator and value |
| `thresholds` | each TH row with the observed value and `PASS` or `FAIL` |
| `findings` | structured failures: code, layer, case, requirement, expected, observed |
| `infrastructure_errors` | cases that ended in an infrastructure error |
| `verdict` | `PASS`, `FAIL` or `INCOMPLETE` |

## Error catalogue

| Code | Exit | Cause |
|------|------|-------|
| `EMPTY_REQUEST` | 1 | FR-002 |
| `REQUEST_TOO_LONG` | 1 | FR-002 |
| `INVALID_NOW` | 1 | FR-003 |
| `INVALID_REMINDERS` | 1 | FR-004 |
| `INVALID_MODEL` | 1 | FR-018 |
| `TRACE_WRITE_ERROR` | 1 | FR-007 |
| `USAGE_ERROR` | 2 | FR-013 |
| `MISSING_API_KEY` | 3 | FR-014 |
| `INVALID_API_BASE` | 3 | FR-014 |
| `INVALID_CONFIG` | 3 | FR-016 (timeout or delay out of range or not a number), key with invalid characters |
| `MODEL_AUTH` | 3 | FR-016: HTTP 401, 403, or 400 about the key |
| `MODEL_NOT_FOUND` | 3 | FR-016: HTTP 404 |
| `MODEL_BAD_REQUEST` | 3 | FR-016: other HTTP 4xx |
| `MODEL_RATE_LIMITED` | 3 | FR-015/016: HTTP 429 after 3 attempts |
| `MODEL_UNAVAILABLE` | 3 | FR-015/016: 5xx or connection failure |
| `MODEL_TIMEOUT` | 3 | FR-015/016: attempt timed out 3 times |
| `MODEL_BLOCKED` | 3 | FR-016: safety block |
| `MODEL_EMPTY` | 3 | FR-016: no candidate text |
| `MODEL_BAD_RESPONSE` | 3 | FR-016: reply is not a JSON object |
| `MODEL_OUTPUT_INVALID` | 3 | FR-006: output violates a rule |
