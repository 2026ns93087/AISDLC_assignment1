"""Dataset loading and checking (the dataset rules of the specification).

A dataset that breaks its own rules makes the evaluation meaningless, so problems are reported
as findings before any model call is made.
"""

import json
from pathlib import Path

from evaluators.layer1 import Json
from evaluators.spec_reader import SpecFacts

MIN_CASES = 15
CATEGORIES = {"normal", "boundary", "ambiguous", "missing_info", "malformed", "adversarial"}
PROPERTIES = {"must_clarify", "must_refuse", "no_canary", "no_invented_target"}
REQUIRED = ("id", "category", "covers", "request", "now", "rationale")
KNOWN_KEYS = set(REQUIRED) | {
    "reminders", "reminders_raw", "expect_error", "intent_in", "expected_due_at",
    "expected_snooze_minutes", "expected_target_id", "title_keywords", "expected_missing",
    "message_terms_any", "properties",
}


def load_cases(path: Path) -> list[Json]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return list(document["cases"])


def case_problems(case: Json, spec: SpecFacts) -> list[str]:
    """Rule violations of one case."""
    name = str(case.get("id", "?"))
    problems = [f"{name}: missing key {key}" for key in REQUIRED if key not in case]
    problems += [f"{name}: unknown key {key}" for key in case if key not in KNOWN_KEYS]
    if case.get("category") not in CATEGORIES:
        problems.append(f"{name}: bad category {case.get('category')!r}")
    covers = case.get("covers")
    if not isinstance(covers, list) or not covers:
        problems.append(f"{name}: covers is empty")
    else:
        unknown = [ident for ident in covers if ident not in spec.ids]
        problems += [f"{name}: covers unknown id {ident}" for ident in unknown]
    for prop in case.get("properties", []):
        if prop not in PROPERTIES:
            problems.append(f"{name}: unknown property {prop}")
    if "expect_error" not in case:
        problems += scored_problems(case, name)
    return problems


def scored_problems(case: Json, name: str) -> list[str]:
    """A scored case needs acceptable intents and, for clarify-only cases, the expected set."""
    problems = []
    if not case.get("intent_in"):
        problems.append(f"{name}: scored case without intent_in")
    clarify_only = case.get("intent_in") == ["clarify"]
    if clarify_only and ("expected_missing" not in case or not case.get("message_terms_any")):
        problems.append(f"{name}: clarify case needs expected_missing and message_terms_any")
    return problems


def dataset_problems(cases: list[Json], spec: SpecFacts) -> list[str]:
    problems = []
    if len(cases) < MIN_CASES:
        problems.append(f"dataset has {len(cases)} cases, at least {MIN_CASES} required")
    identifiers = [str(case.get("id")) for case in cases]
    if len(set(identifiers)) != len(identifiers):
        problems.append("duplicate case ids")
    seen = {str(case.get("category")) for case in cases}
    problems += [f"no case in category {name}" for name in sorted(CATEGORIES - seen)]
    for case in cases:
        problems += case_problems(case, spec)
    return problems
