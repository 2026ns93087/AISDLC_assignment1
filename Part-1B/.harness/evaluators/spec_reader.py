"""Read thresholds, weights, canary token and infrastructure codes from spec.md.

The harness takes these values from the specification so they cannot drift from it
(constitution V). A missing or malformed table is reported, never defaulted.
"""

import re
from dataclasses import dataclass
from pathlib import Path

THRESHOLD_ROW = re.compile(
    r"^\| (TH-\d{3}) \| (MET-\d{3}) \| (==|>=|<=|>|<) \| ([0-9.]+) \|\s*$", re.MULTILINE
)
WEIGHT_ROW = re.compile(r"^\| (W-\d{3}) \| (MET-\d{3}) \| ([0-9.]+) \|\s*$", re.MULTILINE)
CANARY = re.compile(r"\*\*Canary token\*\*: `([A-Za-z0-9-]+)`")
INFRA = re.compile(r"\*\*Infrastructure error codes\*\*:(.*?)\.\s", re.DOTALL)
BACKTICKED = re.compile(r"`([A-Z_]+)`")
SPEC_ID = re.compile(r"\b[A-Z]{1,3}-\d{1,3}\b")


@dataclass(frozen=True)
class Threshold:
    ident: str
    metric: str
    operator: str
    value: float


@dataclass(frozen=True)
class SpecFacts:
    """Everything the evaluation takes from the specification."""

    thresholds: tuple[Threshold, ...]
    weights: dict[str, float]
    canary: str
    infrastructure_codes: frozenset[str]
    ids: frozenset[str]


class SpecError(Exception):
    """The specification does not contain a table the harness needs."""


def read_spec(path: Path) -> SpecFacts:
    text = path.read_text(encoding="utf-8")
    thresholds = tuple(
        Threshold(m.group(1), m.group(2), m.group(3), float(m.group(4)))
        for m in THRESHOLD_ROW.finditer(text)
    )
    weights = {m.group(2): float(m.group(3)) for m in WEIGHT_ROW.finditer(text)}
    canary = CANARY.search(text)
    infra = INFRA.search(text)
    if not thresholds:
        raise SpecError("no threshold rows (TH-nnn) found in spec.md")
    if not weights:
        raise SpecError("no weight rows (W-nnn) found in spec.md")
    if canary is None:
        raise SpecError("no canary token found in spec.md")
    if infra is None:
        raise SpecError("no infrastructure error code list found in spec.md")
    codes = frozenset(BACKTICKED.findall(infra.group(1)))
    return SpecFacts(thresholds, weights, canary.group(1), codes, frozenset(SPEC_ID.findall(text)))
