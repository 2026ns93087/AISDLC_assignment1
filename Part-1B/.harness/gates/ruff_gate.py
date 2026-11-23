"""Gate ruff: zero Ruff findings on src, tests and .harness (NFR-002, NFR-004)."""

import json
import sys

from gates.base import Context, GateResult, relative, run_tool

NAME = "ruff"
REQUIREMENT = "NFR-002, NFR-004"
COMPLEXITY_RULES = frozenset({"C901", "PLR0915", "E501"})


def run(ctx: Context) -> GateResult:
    result = GateResult(NAME)
    targets = [name for name in ("src", "tests", ".harness") if (ctx.root / name).is_dir()]
    command = [sys.executable, "-m", "ruff", "check", *targets, "--no-cache"]
    command += ["--output-format", "json"]
    done = run_tool(command, ctx.root)
    result.stdout = done.stdout
    result.stderr = done.stderr
    if done.code not in (0, 1):
        result.add("TOOL_ERROR", REQUIREMENT, "ruff runs", f"exit {done.code}", stderr=done.stderr)
        return result
    try:
        violations = json.loads(done.stdout or "[]")
    except json.JSONDecodeError as error:
        result.add("TOOL_ERROR", REQUIREMENT, "ruff prints JSON", str(error), stdout=done.stdout)
        return result
    for item in violations:
        code = str(item.get("code"))
        row = item.get("location", {}).get("row", 0)
        requirement = "NFR-004" if code in COMPLEXITY_RULES else "NFR-002"
        result.add(
            f"RUFF_{code}",
            requirement,
            "0 Ruff findings",
            str(item.get("message")),
            location=f"{relative(ctx, item.get('filename', ''))}:{row}",
        )
    return result
