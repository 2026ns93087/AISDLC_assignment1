"""The single evaluation harness for the non-deterministic behaviour (Part 1B).

Pipeline: dataset, agent program (real model), layer 1 structure, layer 2 invariants and
guardrails, layer 3 semantic quality, aggregate score against the thresholds in the
specification, then PASS, FAIL or INCOMPLETE.

Usage:
  python .harness/run_eval.py                      real model (needs GEMINI_API_KEY); evidence
  python .harness/run_eval.py --mode fake          local oracle, to check the harness offline

Real runs are kept under evidence/eval-runs/run-N/ and never overwritten. Fake runs go to
.harness/fake-runs/ (git-ignored) and are labelled `fake` (constitution IX).
Exit codes: 0 PASS, 1 FAIL, 2 setup problem, 3 INCOMPLETE.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import fake_model
from evaluators import dataset, metrics
from evaluators.layer1 import Json
from evaluators.metrics import CaseOutcome
from evaluators.runner import AgentRun, evaluate_case
from evaluators.spec_reader import SpecError, SpecFacts, read_spec
from gates.base import FEATURE_DIR, git_exe, run_tool, sanitize

DEFAULT_HOST = "generativelanguage.googleapis.com"
RUN_FOLDER = re.compile(r"run-(\d+)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key_from_dotenv(root: Path) -> str:
    path = root / ".env"
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        name, _, value = line.strip().removeprefix("export ").partition("=")
        if name.strip() == "GEMINI_API_KEY":
            return value.strip().strip("\"'")
    return ""


def next_run_folder(base: Path) -> tuple[int, Path]:
    """Create the next run-N folder; an existing run is never reused."""
    base.mkdir(parents=True, exist_ok=True)
    taken = [int(m.group(1)) for p in base.iterdir() if (m := RUN_FOLDER.fullmatch(p.name))]
    number = max(taken, default=0) + 1
    while True:
        folder = base / f"run-{number}"
        try:
            folder.mkdir()
        except FileExistsError:
            number += 1
            continue
        return number, folder


def clean_text(value: object, key: str, root: Path) -> object:
    """Sanitise every string: machine paths removed, the API key redacted."""
    if isinstance(value, str):
        text = value.replace(key, "<redacted>") if len(key) >= 8 else value
        return sanitize(text, root)
    if isinstance(value, dict):
        return {name: clean_text(item, key, root) for name, item in value.items()}
    if isinstance(value, list):
        return [clean_text(item, key, root) for item in value]
    return value


def git_state(root: Path) -> dict[str, object]:
    git = git_exe()
    if git is None:
        return {"commit": "unknown", "working_tree_clean": None}
    head = run_tool([git, "rev-parse", "HEAD"], root)
    status = run_tool([git, "status", "--porcelain"], root)
    clean = status.stdout.strip() == "" if status.code == 0 else None
    return {"commit": head.stdout.strip() or "unknown", "working_tree_clean": clean}


def case_findings(case: Json, outcome: CaseOutcome, run: AgentRun) -> list[dict[str, object]]:
    """Structured failure evidence for one case: code, layer, requirement, expected, observed."""
    base = {"case": outcome.case_id, "request": case["request"], "output": run.stdout.strip()[:600]}
    found: list[dict[str, object]] = []
    if outcome.infrastructure_error:
        found.append({**base, "code": outcome.infrastructure_error, "layer": "infrastructure",
                      "requirement": "FR-015", "expected": "a model answer",
                      "observed": run.stderr.strip()[:300]})
    if not outcome.scored and not outcome.error_ok:
        found.append({**base, "code": "INPUT_NOT_REJECTED", "layer": "input",
                      "requirement": ", ".join(map(str, case["covers"])),
                      "expected": json.dumps(case["expect_error"]),
                      "observed": f"exit {run.code}: {run.stderr.strip()[:300]}"})
    for layer, issues in ((1, outcome.layer1), (2, outcome.layer2)):
        found += [{**base, "code": item.code, "layer": layer, "requirement": item.code,
                   "expected": item.expected, "observed": item.observed} for item in issues]
    found += semantic_findings(case, outcome, base)
    found += [{**base, "code": f"GUARDRAIL_{name.upper()}", "layer": 2, "requirement": "MET-007",
               "expected": f"property {name} holds", "observed": "property violated"}
              for name in outcome.properties_failed or []]
    return found


def semantic_findings(
    case: Json, outcome: CaseOutcome, base: dict[str, object]
) -> list[dict[str, object]]:
    meaning = outcome.semantic
    if meaning is None:
        return []
    failed = [
        ("INTENT", "MET-003", meaning.intent_ok is False),
        ("FIELDS", "MET-004", meaning.fields_ok is False),
        ("TITLE", "MET-005", meaning.title_score is not None and meaning.title_score < 1),
        ("CLARIFY", "MET-006", meaning.clarify_ok is False),
    ]
    return [{**base, "code": f"SEMANTIC_{name}", "layer": 3, "requirement": met,
             "expected": f"ground truth of {case['id']}", "observed": "; ".join(meaning.detail)}
            for name, met, bad in failed if bad]


def case_record(case: Json, outcome: CaseOutcome, run: AgentRun) -> dict[str, object]:
    meaning = outcome.semantic
    return {
        "case": outcome.case_id, "category": case["category"], "covers": case["covers"],
        "scored": outcome.scored, "exit_code": run.code,
        "infrastructure_error": outcome.infrastructure_error,
        "layer1_ok": not outcome.layer1, "layer2_ok": not outcome.layer1 and not outcome.layer2,
        "semantic": asdict(meaning) if meaning is not None else None,
        "properties_failed": outcome.properties_failed, "input_rejected_ok": outcome.error_ok,
        "stdout": run.stdout.strip(), "stderr": run.stderr.strip(), "trace": run.trace,
    }


def model_info(records: list[dict[str, object]], mode: str) -> dict[str, object]:
    traces = [r["trace"] for r in records if isinstance(r["trace"], dict)]
    names = sorted({str(t["model"]) for t in traces if t.get("model")})
    versions = sorted({str(t["model_version"]) for t in traces if t.get("model_version")})
    usages = [t["usage"] for t in traces if isinstance(t.get("usage"), dict)]
    tokens = sum(int(usage.get("totalTokenCount", 0)) for usage in usages)
    host = DEFAULT_HOST if mode == "real" else "local fake"
    return {"requested": names, "reported_versions": versions, "temperature": 0,
            "response_type": "application/json", "api_host": host, "total_tokens": tokens}


def metric_table(found: dict[str, metrics.Metric]) -> dict[str, object]:
    return {
        ident: {"name": item.name, "numerator": round(item.numerator, 4),
                "denominator": item.denominator,
                "value": None if item.value is None else round(item.value, 4)}
        for ident, item in sorted(found.items())
    }


Records = list[dict[str, object]]


def evaluate_all(
    cases: list[Json],
    args: argparse.Namespace,
    root: Path,
    spec: SpecFacts,
    environment: dict[str, str],
) -> tuple[list[CaseOutcome], Records, Records]:
    outcomes: list[CaseOutcome] = []
    records: list[dict[str, object]] = []
    findings: list[dict[str, object]] = []
    for index, case in enumerate(cases):
        outcome, run = evaluate_case(case, root, environment, args.model, spec)
        outcomes.append(outcome)
        records.append(case_record(case, outcome, run))
        findings += case_findings(case, outcome, run)
        print(f"  {outcome.case_id:<7} {status_word(outcome)}", flush=True)
        if args.pause and index < len(cases) - 1 and args.mode == "real":
            time.sleep(args.pause)
    return outcomes, records, findings


def status_word(outcome: CaseOutcome) -> str:
    if outcome.infrastructure_error:
        return f"INFRA  {outcome.infrastructure_error}"
    if not outcome.scored:
        return "ok" if outcome.error_ok else "FAIL   input not rejected"
    bad = outcome.layer1 or outcome.layer2 or outcome.properties_failed
    meaning = outcome.semantic
    soft = meaning is not None and (meaning.intent_ok is False or meaning.fields_ok is False)
    return "FAIL" if bad else ("sem?   semantic difference" if soft else "ok")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the single evaluation harness.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--mode", choices=("real", "fake"), default="real")
    parser.add_argument("--model", default=None)
    parser.add_argument("--pause", type=float, default=4.0, help="seconds between real calls")
    parser.add_argument("--defect", choices=fake_model.DEFECTS, default="none")
    parser.add_argument("--every", type=int, default=4, help="fake defect on every Nth request")
    parser.add_argument("--only", default=None, help="comma-separated case ids (debugging only)")
    return parser.parse_args(argv)


def real_environment(root: Path) -> tuple[dict[str, str], str] | str:
    """The environment for a real run and the key, or an explanation of what is wrong."""
    environment = dict(os.environ)
    base = environment.get("REMINDER_AGENT_API_BASE", "")
    if base and DEFAULT_HOST not in base:
        return "a real run must use the Gemini host; unset REMINDER_AGENT_API_BASE"
    key = environment.get("GEMINI_API_KEY", "").strip() or key_from_dotenv(root)
    if not key:
        return "GEMINI_API_KEY is not set (environment or .env)"
    return environment, key


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.resolve()
    try:
        spec = read_spec(root / FEATURE_DIR / "spec.md")
        cases = dataset.load_cases(root / "evals" / "dataset.json")
    except (SpecError, OSError, ValueError, KeyError) as error:
        print(f"SETUP ERROR: {error}")
        return 2
    problems = dataset.dataset_problems(cases, spec)
    if problems:
        print("DATASET ERROR:\n  " + "\n  ".join(problems))
        return 2
    server = None
    if args.mode == "fake":
        server = fake_model.start(cases, args.defect, args.every)
        key = "fake-key-ABCDEFGH12345678"
        environment = dict(os.environ)
        environment.update({"GEMINI_API_KEY": key, "REMINDER_AGENT_RETRY_DELAY": "0",
                            "REMINDER_AGENT_ENV_FILE": str(root / "no-such.env"),
                            "REMINDER_AGENT_API_BASE": f"http://127.0.0.1:{server.server_port}"})
    else:
        prepared = real_environment(root)
        if isinstance(prepared, str):
            print(f"SETUP ERROR: {prepared}")
            return 2
        environment, key = prepared
    if args.only:
        wanted = set(args.only.split(","))
        cases = [case for case in cases if case["id"] in wanted]
    base = root / ".harness" / "fake-runs"
    if args.mode == "real":
        base = root / "evidence" / "eval-runs"
    number, folder = next_run_folder(base)
    print(f"Evaluation run {number} ({args.mode} mode), {len(cases)} cases")
    try:
        outcomes, records, findings = evaluate_all(cases, args, root, spec, environment)
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()
    found = metrics.metric_list(outcomes)
    found["MET-008"] = metrics.semantic_score(found, spec.weights)
    decisions = metrics.decide(found, spec)
    result = metrics.verdict(decisions, outcomes)
    report = {
        "run": number, "mode": args.mode,
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "defect_injected": args.defect if args.mode == "fake" else "none",
        "model": model_info(records, args.mode),
        "inputs": {"dataset_sha256": sha256(root / "evals" / "dataset.json"),
                   "system_prompt_sha256": sha256(root / "prompts" / "system.md"),
                   "spec_sha256": sha256(root / FEATURE_DIR / "spec.md"),
                   "cases": len(cases)},
        "git": git_state(root), "metrics": metric_table(found), "thresholds": decisions,
        "verdict": result, "findings": findings,
        "infrastructure_errors": [r["case"] for r in records if r["infrastructure_error"]],
        "cases": records,
    }
    text = json.dumps(clean_text(report, key, root), indent=2, ensure_ascii=True) + "\n"
    (folder / "eval-results.json").write_bytes(text.encode("utf-8"))
    print_summary(found, decisions, result, findings)
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 3}[result]


def print_summary(found: dict[str, metrics.Metric], decisions: list[dict[str, object]],
                  result: str, findings: list[dict[str, object]]) -> None:
    print("Metrics")
    for ident, item in sorted(found.items()):
        shown = "n/a" if item.value is None else f"{item.value:.3f}"
        print(f"  {ident} {item.name:<24} {shown}  ({item.numerator:g}/{item.denominator})")
    print("Thresholds")
    for row in decisions:
        label = f"{row['threshold']} {row['metric']} {row['required']:<8}"
        print(f"  {label} observed {row['observed']}  {row['status']}")
    print(f"Findings: {len(findings)}")
    print(f"VERDICT: {result}")


if __name__ == "__main__":
    sys.exit(main())
