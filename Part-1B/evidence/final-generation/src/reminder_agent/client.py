"""Model client: one POST to the Gemini REST API, with retries (FR-014 to FR-016).

Uses `http.client` from the standard library. The key goes only in the `x-goog-api-key` header,
never in the URL or the body.
"""

import http.client
import json
import re
import ssl
import time
from dataclasses import dataclass

from reminder_agent.config import Settings, redact
from reminder_agent.errors import AppError

MAX_ATTEMPTS = 3
MAX_BODY = 4_000_000
TRANSIENT_STATUS = {429: "MODEL_RATE_LIMITED", 500: "MODEL_UNAVAILABLE", 502: "MODEL_UNAVAILABLE",
                    503: "MODEL_UNAVAILABLE", 504: "MODEL_UNAVAILABLE"}
BLOCKED_FINISH = frozenset({"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "RECITATION"})
KEY_COMPLAINT = re.compile(r"api[ _-]?key", re.IGNORECASE)
CONTROL = re.compile(r"[\x00-\x1f\x7f]")


class ModelError(AppError):
    """A model or infrastructure failure, with what the trace needs to know."""

    def __init__(
        self,
        code: str,
        message: str,
        attempts: int,
        finish_reason: str | None = None,
        model_version: str | None = None,
    ) -> None:
        super().__init__(code, message, 3)
        self.attempts = attempts
        self.finish_reason = finish_reason
        self.model_version = model_version


@dataclass(frozen=True)
class Transient:
    """A failure that is worth another attempt."""

    code: str
    message: str


@dataclass(frozen=True)
class ModelReply:
    """A usable reply: the model text and the facts the trace records."""

    text: str
    model_version: str | None
    finish_reason: str | None
    usage: dict[str, object] | None
    attempts: int


def request_body(system_text: str, user_text: str) -> bytes:
    """The JSON body of `generateContent` (contracts/cli-contract.md)."""
    body = {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    return json.dumps(body).encode("utf-8")


def open_connection(settings: Settings) -> http.client.HTTPConnection:
    target = settings.target
    if target.scheme == "https":
        context = ssl.create_default_context()
        return http.client.HTTPSConnection(
            target.host, target.port, timeout=settings.timeout, context=context
        )
    return http.client.HTTPConnection(target.host, target.port, timeout=settings.timeout)


def service_message(data: bytes, settings: Settings) -> str:
    """A short, safe description of an error body: the service message with the key removed."""
    try:
        document = json.loads(data.decode("utf-8", errors="replace"))
        text = str(document["error"]["message"])
    except (ValueError, KeyError, TypeError):
        text = ""
    text = CONTROL.sub(" ", redact(text, settings.api_key))
    return text[:200]


def classify_error(status: int, data: bytes, settings: Settings, attempt: int) -> Transient:
    """Map an HTTP error status to a transient failure or raise the permanent error."""
    detail = service_message(data, settings)
    suffix = f" (HTTP {status}: {detail})" if detail else f" (HTTP {status})"
    if status in TRANSIENT_STATUS:
        return Transient(TRANSIENT_STATUS[status], "The model service failed" + suffix)
    haystack = data.decode("utf-8", errors="replace")
    if status in (401, 403) or (status == 400 and KEY_COMPLAINT.search(haystack)):
        raise ModelError("MODEL_AUTH", "The API key was rejected" + suffix, attempt)
    if status == 404:
        raise ModelError("MODEL_NOT_FOUND", "Model or method not found" + suffix, attempt)
    if 400 <= status < 500:
        raise ModelError("MODEL_BAD_REQUEST", "The request was rejected" + suffix, attempt)
    raise ModelError("MODEL_UNAVAILABLE", "The model service failed" + suffix, attempt)


def candidate_text(candidate: dict[str, object]) -> str:
    """The text parts of a candidate, joined; thought parts are skipped."""
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    texts = []
    for part in parts if isinstance(parts, list) else []:
        if isinstance(part, dict) and isinstance(part.get("text"), str) and not part.get("thought"):
            texts.append(part["text"])
    return "".join(texts)


def read_reply(data: bytes, attempt: int) -> ModelReply:
    """Turn a 200 reply into text, or raise MODEL_BAD_RESPONSE, MODEL_BLOCKED or MODEL_EMPTY."""
    try:
        document = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        document = None
    if not isinstance(document, dict):
        raise ModelError("MODEL_BAD_RESPONSE", "The reply is not a JSON object.", attempt)
    version = document.get("modelVersion")
    version = version if isinstance(version, str) else None
    feedback = document.get("promptFeedback")
    if isinstance(feedback, dict) and feedback.get("blockReason"):
        raise ModelError("MODEL_BLOCKED", "The prompt was blocked by the service.", attempt,
                         str(feedback["blockReason"]), version)
    candidates = document.get("candidates")
    first = candidates[0] if isinstance(candidates, list) and candidates else None
    if not isinstance(first, dict):
        raise ModelError("MODEL_EMPTY", "The reply has no candidate.", attempt, None, version)
    finish = first.get("finishReason")
    finish = finish if isinstance(finish, str) else None
    if finish in BLOCKED_FINISH:
        raise ModelError("MODEL_BLOCKED", "The reply was blocked.", attempt, finish, version)
    text = candidate_text(first)
    if not text.strip():
        raise ModelError("MODEL_EMPTY", "The reply has no text.", attempt, finish, version)
    usage = document.get("usageMetadata")
    return ModelReply(text, version, finish, usage if isinstance(usage, dict) else None, attempt)


def exchange(settings: Settings, body: bytes, attempt: int) -> ModelReply | Transient:
    """One HTTP round trip. Returns a reply, or a transient failure to retry."""
    path = f"/v1beta/models/{settings.model}:generateContent"
    headers = {"content-type": "application/json", "x-goog-api-key": settings.api_key}
    connection = open_connection(settings)
    try:
        connection.request("POST", path, body=body, headers=headers)
        response = connection.getresponse()
        status = response.status
        data = response.read(MAX_BODY + 1)
    except TimeoutError:
        return Transient("MODEL_TIMEOUT", "The model did not answer in time.")
    except ssl.SSLCertVerificationError as error:
        message = "TLS certificate check failed; see the README section on proxies."
        raise ModelError("MODEL_UNAVAILABLE", message, attempt) from error
    except (OSError, http.client.HTTPException):
        return Transient("MODEL_UNAVAILABLE", "The model service cannot be reached.")
    finally:
        connection.close()
    if len(data) > MAX_BODY:
        raise ModelError("MODEL_BAD_RESPONSE", "The reply is too large.", attempt)
    if status == 200:
        return read_reply(data, attempt)
    if 200 <= status < 400:
        raise ModelError("MODEL_BAD_RESPONSE", f"Unexpected HTTP status {status}.", attempt)
    return classify_error(status, data, settings, attempt)


def generate(settings: Settings, system_text: str, user_text: str) -> ModelReply:
    """Call the model, with at most 3 attempts and a doubling delay (FR-015)."""
    body = request_body(system_text, user_text)
    failure = Transient("MODEL_UNAVAILABLE", "No attempt was made.")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        outcome = exchange(settings, body, attempt)
        if isinstance(outcome, ModelReply):
            return outcome
        failure = outcome
        if attempt < MAX_ATTEMPTS:
            time.sleep(settings.delay * 2 ** (attempt - 1))
    raise ModelError(failure.code, failure.message, MAX_ATTEMPTS)
