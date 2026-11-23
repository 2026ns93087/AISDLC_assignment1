"""Layer 3: semantic quality against ground truth stored in the dataset (MET-003 to MET-006).

No language model is used as a judge (constitution IV). Scores are computed from exact values,
keyword groups and sets, so a run can be re-scored by hand.
"""

from dataclasses import dataclass

from evaluators.layer1 import Json

STATED_FIELDS = (
    ("expected_due_at", "due_at"),
    ("expected_snooze_minutes", "snooze_minutes"),
    ("expected_target_id", "target_id"),
)


@dataclass(frozen=True)
class Semantic:
    """Layer 3 result for one case. A value of None means the metric does not apply."""

    intent_ok: bool | None
    fields_ok: bool | None
    title_score: float | None
    clarify_ok: bool | None
    detail: list[str]


def stated_fields(case: Json) -> list[tuple[str, str]]:
    return [(key, field) for key, field in STATED_FIELDS if key in case]


def intent_matches(case: Json, document: Json | None) -> bool:
    allowed = case.get("intent_in", [])
    return document is not None and document.get("intent") in allowed


def fields_match(case: Json, document: Json | None, detail: list[str]) -> bool:
    """Every stated expected value equals the output exactly."""
    if document is None:
        detail.append("no valid output")
        return False
    ok = True
    for key, field in stated_fields(case):
        if document.get(field) != case[key]:
            detail.append(f"{field}: expected {case[key]!r}, observed {document.get(field)!r}")
            ok = False
    return ok


def group_found(group: str, title: str) -> bool:
    lowered = title.lower()
    return any(word.strip().lower() in lowered for word in group.split("|") if word.strip())


def title_fraction(case: Json, document: Json | None, detail: list[str]) -> float:
    """Fraction of keyword groups found in the title; a missing title scores 0."""
    groups = [str(group) for group in case["title_keywords"]]
    title = document.get("title") if document is not None else None
    if not isinstance(title, str):
        detail.append("no title in the output")
        return 0.0
    found = [group for group in groups if group_found(group, title)]
    for group in groups:
        if group not in found:
            detail.append(f"title {title!r} lacks keyword group {group!r}")
    return len(found) / len(groups)


def clarification_matches(case: Json, document: Json | None, detail: list[str]) -> bool:
    """`missing` equals the expected set and the message holds one of the expected terms."""
    if document is None:
        detail.append("no valid output")
        return False
    observed = document.get("missing")
    expected = set(case.get("expected_missing", []))
    set_ok = isinstance(observed, list) and set(map(str, observed)) == expected
    message = document.get("message")
    terms = [str(term).lower() for term in case.get("message_terms_any", [])]
    text_ok = isinstance(message, str) and any(term in message.lower() for term in terms)
    if not set_ok:
        detail.append(f"missing: expected {sorted(expected)}, observed {observed!r}")
    if not text_ok:
        detail.append(f"message {message!r} holds none of {terms}")
    return set_ok and text_ok


def score_case(case: Json, document: Json | None) -> Semantic:
    """Layer 3 for one scored case."""
    detail: list[str] = []
    intent_ok = intent_matches(case, document)
    if not intent_ok:
        observed = document.get("intent") if document is not None else None
        detail.append(f"intent: expected one of {case.get('intent_in')}, observed {observed!r}")
    fields_ok = fields_match(case, document, detail) if stated_fields(case) else None
    title_score = title_fraction(case, document, detail) if "title_keywords" in case else None
    clarify_only = case.get("intent_in") == ["clarify"]
    clarify_ok = clarification_matches(case, document, detail) if clarify_only else None
    return Semantic(intent_ok, fields_ok, title_score, clarify_ok, detail)
