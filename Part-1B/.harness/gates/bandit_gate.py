"""Gate bandit: zero Bandit findings of any severity in src (NFR-003)."""

import json
import sys

from gates.base import Context, GateResult, relative, run_tool

NAME = "bandit"
REQUIREMENT = "NFR-003"


def run(ctx: Context) -> GateResult:
    result = GateResult(NAME)
    if not ctx.src.is_dir():
        result.add("SRC_MISSING", REQUIREMENT, "src/ exists", "directory not found")
        return result
    command = [sys.executable, "-m", "bandit", "-r", "src", "-f", "json", "-q"]
    done = run_tool(command, ctx.root)
    result.stdout = done.stdout
    result.stderr = done.stderr
    if done.code not in (0, 1):
        result.add(
            "TOOL_ERROR", REQUIREMENT, "bandit runs", f"exit {done.code}", stderr=done.stderr
        )
        return result
    try:
        report = json.loads(done.stdout)
    except json.JSONDecodeError as error:
        result.add("TOOL_ERROR", REQUIREMENT, "bandit prints JSON", str(error), stdout=done.stdout)
        return result
    for item in report.get("results", []):
        severity = f"{item.get('issue_severity')}/{item.get('issue_confidence')}"
        result.add(
            f"BANDIT_{item.get('test_id')}",
            REQUIREMENT,
            "0 Bandit findings",
            f"{severity}: {item.get('issue_text')}",
            location=f"{relative(ctx, item.get('filename', ''))}:{item.get('line_number')}",
        )
    for item in report.get("errors", []):
        result.add(
            "BANDIT_ERROR",
            REQUIREMENT,
            "every file scanned",
            str(item.get("reason")),
            location=relative(ctx, item.get("filename", "")),
        )
    return result
