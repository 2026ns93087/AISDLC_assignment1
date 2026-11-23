# CLI Contract: `python -m reminder_agent`

## Synopsis

```
python -m reminder_agent [--now T] [--reminders FILE] [--model NAME] [--trace FILE] [--] REQUEST...
```

`REQUEST...` is one or more words joined by single spaces (FR-002). A request that starts with a
dash is passed after `--` (D-9).

## Options

| Option | Default | Rule |
|--------|---------|------|
| `--now T` | system clock, local offset | `YYYY-MM-DDTHH:MM:SS+HH:MM` (FR-003) |
| `--reminders FILE` | none | JSON array, at most 20 items (FR-004) |
| `--model NAME` | `GEMINI_MODEL`, else `gemini-flash-latest` | `[A-Za-z0-9._-]{1,64}` (FR-018) |
| `--trace FILE` | none | write the trace object (FR-007) |

## Environment

| Name | Meaning | Default |
|------|---------|---------|
| `GEMINI_API_KEY` | API key (never printed, never traced) | none, required |
| `GEMINI_MODEL` | model name | `gemini-flash-latest` |
| `REMINDER_AGENT_API_BASE` | API base URL | `https://generativelanguage.googleapis.com` |
| `REMINDER_AGENT_TIMEOUT` | seconds per attempt, 1 to 600 | 60 |
| `REMINDER_AGENT_RETRY_DELAY` | seconds before the first retry, 0 to 60 | 5 |
| `REMINDER_AGENT_ENV_FILE` | path of the `.env` file to read (only that file) | `./.env`, then project root `.env` |

Process environment wins over the `.env` file (FR-017).

## Output

- Success: one JSON object and `\n` on stdout, nothing on stderr, exit 0.
- Failure: nothing on stdout, one JSON error object and `\n` on stderr.

## Exit codes

`0` success, `1` invalid request or input, `2` usage error, `3` model, configuration or
infrastructure error. Error codes: `data-model.md`, Error catalogue.

## HTTP mapping (FR-016)

| Condition | Code | Retried (FR-015) |
|-----------|------|------------------|
| 200, usable text | none | n/a |
| 200, `promptFeedback.blockReason` or finish reason `SAFETY`, `BLOCKLIST`, `PROHIBITED_CONTENT`, `SPII`, `RECITATION` | `MODEL_BLOCKED` | no |
| 200, no candidate or no text | `MODEL_EMPTY` | no |
| 200, body not a JSON object | `MODEL_BAD_RESPONSE` | no |
| 400 mentioning the key | `MODEL_AUTH` | no |
| 400 other | `MODEL_BAD_REQUEST` | no |
| 401, 403 | `MODEL_AUTH` | no |
| 404 | `MODEL_NOT_FOUND` | no |
| 429 | `MODEL_RATE_LIMITED` | yes |
| 500, 502, 503, 504 | `MODEL_UNAVAILABLE` | yes |
| other 4xx | `MODEL_BAD_REQUEST` | no |
| other 5xx | `MODEL_UNAVAILABLE` | no |
| connection failure | `MODEL_UNAVAILABLE` | yes |
| timeout | `MODEL_TIMEOUT` | yes |

## Request sent to the model

`POST {base}/v1beta/models/{model}:generateContent`, headers `content-type: application/json` and
`x-goog-api-key: <key>`. Body:

```json
{
  "systemInstruction": {"parts": [{"text": "<prompts/system.md>"}]},
  "contents": [{"role": "user", "parts": [{"text": "<user message>"}]}],
  "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}
}
```

The user message contains, in this order: the reference time and weekday, the UTC offset, the latest
allowed time, a 15-line calendar (today and the 14 following days), the existing reminders as JSON,
and the request between `<request>` and `</request>`.
