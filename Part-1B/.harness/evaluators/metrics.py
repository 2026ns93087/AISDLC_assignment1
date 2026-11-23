"""Aggregate decision: MET-001 to MET-009, thresholds TH-001 to TH-006 and the verdict.

A metric is a numerator and a denominator. A metric with no applicable case has a value of None
and a threshold on it is reported as not evaluable, which is a FAIL (never a silent pass).
"""

import operator
from collections.abc import Callable
from dataclasses import dataclass, field

from evaluators.layer1 import Issue
from evaluators.layer3 import Semantic
from evaluators.spec_reader import SpecFacts, Threshold

COMPARE: dict[str, Callable[[float, float], bool]] = {
    "==": lambda a, b: abs(a - b) < 1e-9,
    ">=": lambda a, b: a >= b - 1e-9,
    "<=": lambda a, b: a <= b + 1e-9,
    ">": operator.gt,
    "<": operator.lt,
}
SEMANTIC_PARTS = {
    "MET-003": "intent",
    "MET-004": "fields",
    "MET-005": "title",
    "MET-006": "clarify",
}


@dataclass
class CaseOutcome:
    """Everything the metrics need to know about one case."""

    case_id: str
    scored: bool
    infrastructure_error: str | None = None
    layer1: list[Issue] = field(default_factory=list)
    layer2: list[Issue] = field(default_factory=list)
    semantic: Semantic | None = None
    properties_failed: list[str] | None = None
    error_ok: bool | None = None


@dataclass(frozen=True)
class Metric:
    ident: str
    name: str
    numerator: float
    denominator: int

    @property
    def value(self) -> float | None:
        return self.numerator / self.denominator if self.denominator else None


def ratio(ident: str, name: str, flags: list[bool]) -> Metric:
    return Metric(ident, name, float(sum(flags)), len(flags))


def completed(outcomes: list[CaseOutcome]) -> list[CaseOutcome]:
    return [item for item in outcomes if item.infrastructure_error is None]


def semantic_flags(outcomes: list[CaseOutcome], part: str) -> list[bool | float]:
    """Per-case values of one semantic part, for the cases where it applies."""
    values: list[bool | float] = []
    for item in outcomes:
        meaning = item.semantic
        if item.scored and meaning is not None:
            value = getattr(meaning, SEMANTIC_PARTS_ATTR[part])
            if value is not None:
                values.append(value)
    return values


SEMANTIC_PARTS_ATTR = {
    "intent": "intent_ok",
    "fields": "fields_ok",
    "title": "title_score",
    "clarify": "clarify_ok",
}


def metric_list(outcomes: list[CaseOutcome]) -> dict[str, Metric]:
    """MET-001 to MET-007 and MET-009 from the case outcomes (MET-008 comes after)."""
    scored = [item for item in completed(outcomes) if item.scored]
    errors = [item for item in completed(outcomes) if not item.scored]
    metrics = {
        "MET-001": ratio("MET-001", "structural validity", [not i.layer1 for i in scored]),
        "MET-002": ratio(
            "MET-002", "invariant rate", [not i.layer1 and not i.layer2 for i in scored]
        ),
        "MET-009": ratio("MET-009", "input rejection", [bool(i.error_ok) for i in errors]),
    }
    for ident, part in SEMANTIC_PARTS.items():
        values = semantic_flags(scored, part)
        names = {"MET-003": "intent accuracy", "MET-004": "field accuracy",
                 "MET-005": "title fidelity", "MET-006": "clarification accuracy"}
        metrics[ident] = Metric(ident, names[ident], float(sum(values)), len(values))
    with_properties = [i for i in scored if i.properties_failed is not None]
    metrics["MET-007"] = ratio(
        "MET-007", "guardrail rate", [not i.properties_failed for i in with_properties]
    )
    return metrics


def semantic_score(metrics: dict[str, Metric], weights: dict[str, float]) -> Metric:
    """MET-008: weighted sum. A part with no applicable case contributes 0 and is reported."""
    total = 0.0
    for ident, weight in weights.items():
        value = metrics[ident].value
        total += weight * (value if value is not None else 0.0)
    return Metric("MET-008", "semantic score", total, 1)


def decide(
    metrics: dict[str, Metric], spec: SpecFacts
) -> list[dict[str, object]]:
    """One record per threshold: required, observed and PASS or FAIL."""
    records: list[dict[str, object]] = []
    for threshold in spec.thresholds:
        records.append(threshold_record(threshold, metrics.get(threshold.metric)))
    return records


def threshold_record(threshold: Threshold, metric: Metric | None) -> dict[str, object]:
    value = metric.value if metric is not None else None
    ok = value is not None and COMPARE[threshold.operator](value, threshold.value)
    return {
        "threshold": threshold.ident,
        "metric": threshold.metric,
        "required": f"{threshold.operator} {threshold.value:g}",
        "observed": None if value is None else round(value, 4),
        "status": "PASS" if ok else "FAIL",
    }


def verdict(records: list[dict[str, object]], outcomes: list[CaseOutcome]) -> str:
    """INCOMPLETE on any infrastructure error, else PASS only if every threshold holds."""
    if any(item.infrastructure_error is not None for item in outcomes):
        return "INCOMPLETE"
    return "PASS" if all(record["status"] == "PASS" for record in records) else "FAIL"
