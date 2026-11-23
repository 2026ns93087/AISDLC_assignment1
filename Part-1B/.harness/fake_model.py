"""A local stand-in for the Gemini API, used ONLY to check the harness offline.

It looks the request up in the dataset and answers from the ground truth ("oracle"), optionally
with injected defects so that every failure path of the harness can be shown. Results produced
with it are labelled `fake` and are never evidence (constitution IX).
"""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from evaluators.layer1 import Json

REQUEST_BLOCK = re.compile(r"<request>\n(.*?)\n</request>", re.DOTALL)
DEFECTS = ("none", "invalid-json", "canary", "wrong-time", "bad-intent", "outage")
CANARY = "RA-CANARY-4417"


def first_alternative(group: str) -> str:
    return group.split("|")[0].strip()


def blank_result() -> Json:
    return {
        "intent": "unsupported", "title": None, "due_at": None, "target_id": None,
        "snooze_minutes": None, "missing": [], "message": None,
    }


def ideal_result(case: Json) -> Json:
    """The reply a perfect model would give for a scored case."""
    intents = list(case.get("intent_in", ["unsupported"]))
    intent = "unsupported" if "unsupported" in intents else intents[0]
    result = blank_result()
    result["intent"] = intent
    if intent == "create":
        words = [first_alternative(str(group)) for group in case.get("title_keywords", ["task"])]
        result["title"] = " ".join(words).capitalize()
        result["due_at"] = case.get("expected_due_at")
    elif intent == "reschedule":
        result["target_id"] = case.get("expected_target_id")
        result["due_at"] = case.get("expected_due_at")
    elif intent == "snooze":
        result["target_id"] = case.get("expected_target_id")
        result["snooze_minutes"] = case.get("expected_snooze_minutes")
    elif intent == "clarify":
        result["missing"] = list(case.get("expected_missing", []))
        terms = case.get("message_terms_any", ["when"])
        result["message"] = f"Could you tell me more: {terms[0]}?"
    else:
        result["message"] = "I can only create, reschedule or snooze reminders."
    return result


def apply_defect(result: Json, defect: str) -> str:
    """The reply text after injecting a defect."""
    if defect == "invalid-json":
        return "Sure, I will remind you!"
    if defect == "canary":
        field = "title" if result["title"] is not None else "message"
        result[field] = f"{result[field] or 'note'} {CANARY}"
    if defect == "wrong-time" and isinstance(result["due_at"], str):
        text = result["due_at"]
        result["due_at"] = text[:11] + f"{(int(text[11:13]) + 1) % 24:02d}" + text[13:]
    if defect == "bad-intent":
        result["intent"] = "unsupported" if result["intent"] != "unsupported" else "create"
    return json.dumps(result)


class Oracle:
    """Answers requests from the dataset. Thread-safe request counter for defect scheduling."""

    def __init__(self, cases: list[Json], defect: str, every: int) -> None:
        scored = [case for case in cases if "expect_error" not in case]
        self.by_request = {str(case["request"]): case for case in scored}
        self.defect = defect
        self.every = every
        self.count = 0
        self.lock = threading.Lock()

    def answer(self, request: str) -> tuple[int, bytes]:
        with self.lock:
            self.count += 1
            number = self.count
        defective = self.defect != "none" and number % self.every == 0
        if defective and self.defect == "outage":
            return 503, b'{"error": {"code": 503, "message": "simulated outage"}}'
        case = self.by_request.get(request)
        result = ideal_result(case) if case is not None else blank_result()
        if case is None:
            result["message"] = "I can only create, reschedule or snooze reminders."
        text = apply_defect(result, self.defect if defective else "none")
        body = {
            "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
            "modelVersion": "fake-oracle",
            "usageMetadata": {"totalTokenCount": 0},
        }
        return 200, json.dumps(body).encode("utf-8")


def start(cases: list[Json], defect: str = "none", every: int = 4) -> ThreadingHTTPServer:
    """Start the fake service on a free loopback port; the caller stops it."""
    oracle = Oracle(cases, defect, every)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            user_text = str(payload["contents"][0]["parts"][0]["text"])
            block = REQUEST_BLOCK.search(user_text)
            status, data = oracle.answer(block.group(1) if block else "")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
