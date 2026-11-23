"""Run one evaluation case: the agent as a program, then the three layers.

The harness never imports the agent (constitution IV). It starts it with the same command a
person would use and judges what comes out.
"""

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from evaluators import layer1, layer2, layer3
from evaluators.layer1 import Json
from evaluators.metrics import CaseOutcome
from evaluators.spec_reader import SpecFacts

AGENT_TIMEOUT = 600


@dataclass(frozen=True)
class AgentRun:
    """What the agent program did for one request."""

    code: int
    stdout: str
    stderr: str
    trace: Json | None


def agent_command(
    case: Json, reminders_path: str | None, trace_path: str, model: str | None
) -> list[str]:
    command = [sys.executable, "-m", "reminder_agent", "--now", str(case["now"])]
    command += ["--trace", trace_path]
    if reminders_path is not None:
        command += ["--reminders", reminders_path]
    if model:
        command += ["--model", model]
    return [*command, "--", str(case["request"])]


def write_reminders(case: Json, folder: Path) -> str | None:
    if "reminders_raw" in case:
        target = folder / "reminders.json"
        target.write_text(str(case["reminders_raw"]), encoding="utf-8", newline="\n")
        return str(target)
    if "reminders" in case:
        target = folder / "reminders.json"
        target.write_text(json.dumps(case["reminders"]), encoding="utf-8", newline="\n")
        return str(target)
    return None


def run_agent(case: Json, root: Path, environment: dict[str, str], model: str | None) -> AgentRun:
    """Start the agent once for a case and collect its output and trace."""
    with tempfile.TemporaryDirectory() as folder_name:
        folder = Path(folder_name)
        trace_path = folder / "trace.json"
        command = agent_command(case, write_reminders(case, folder), str(trace_path), model)
        env = dict(environment)
        env["PYTHONPATH"] = str(root / "src")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            done = subprocess.run(
                command,
                capture_output=True,
                env=env,
                cwd=folder,
                timeout=AGENT_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return AgentRun(124, "", "harness timeout", None)
        trace = None
        if trace_path.is_file():
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
        return AgentRun(
            done.returncode,
            done.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n"),
            done.stderr.decode("utf-8", errors="replace").replace("\r\n", "\n"),
            trace,
        )


def error_code_of(run: AgentRun) -> str | None:
    try:
        document = json.loads(run.stderr)
        return str(document["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return None


def reminder_ids(case: Json) -> set[str]:
    return {str(item["id"]) for item in case.get("reminders", [])}


def evaluate_error_case(case: Json, run: AgentRun) -> CaseOutcome:
    """Cases that must be rejected before the model is called (MET-009)."""
    expected = case["expect_error"]
    code = error_code_of(run)
    exit_ok = run.code == expected["exit_code"] and run.stdout == "" and code == expected["code"]
    return CaseOutcome(str(case["id"]), scored=False, error_ok=exit_ok)


def evaluate_scored_case(case: Json, run: AgentRun, spec: SpecFacts) -> CaseOutcome:
    """Layers 1, 2 and 3 for a case that expects a result."""
    outcome = CaseOutcome(str(case["id"]), scored=True)
    code = error_code_of(run)
    if run.code != 0:
        if code in spec.infrastructure_codes:
            outcome.infrastructure_error = code
            return outcome
        reason = f"exit {run.code}, error {code}"
        outcome.layer1 = [layer1.Issue(1, "NO_OUTPUT", "exit 0 and a JSON object", reason)]
        return finish_scored(outcome, case, None, spec)
    document, issues = layer1.structure_of(run.stdout)
    outcome.layer1 = issues
    if document is not None and not issues:
        outcome.layer2 = layer2.check_invariants(
            document, str(case["now"]), reminder_ids(case), spec.canary
        )
    return finish_scored(outcome, case, document if not issues else None, spec)


def finish_scored(
    outcome: CaseOutcome, case: Json, document: Json | None, spec: SpecFacts
) -> CaseOutcome:
    """Layer 3 and the guardrail properties, for a case with or without a usable output."""
    outcome.semantic = layer3.score_case(case, document)
    names = [str(name) for name in case.get("properties", [])]
    if names:
        outcome.properties_failed = layer2.failed_properties(
            names, document, reminder_ids(case), spec.canary
        )
    return outcome


def evaluate_case(
    case: Json, root: Path, environment: dict[str, str], model: str | None, spec: SpecFacts
) -> tuple[CaseOutcome, AgentRun]:
    run = run_agent(case, root, environment, model)
    if "expect_error" in case:
        return evaluate_error_case(case, run), run
    return evaluate_scored_case(case, run, spec), run
