"""Run every static gate in the fixed order of plan PD-9 and keep the evidence.

Usage: python .harness/run_harness.py [--root DIR] [--results-dir DIR] [--baseline-tag TAG]

Every run goes to its own folder run-N under evidence/gate-runs/ and is never
overwritten (constitution VII). All gates always run; none stops the others (PD-9).
The exit code is 0 only when every gate passes.
"""

import argparse
import json
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

from gates import (
    bandit_gate,
    banned_calls,
    integrity,
    ruff_gate,
    secret_path_scan,
    stdlib_imports,
    tests_gate,
    traceability,
)
from gates.base import BASELINE_TAG, Context, Finding, GateResult, git_exe, run_tool, sanitize

GATES: tuple[ModuleType, ...] = (
    integrity,
    secret_path_scan,
    stdlib_imports,
    banned_calls,
    ruff_gate,
    bandit_gate,
    tests_gate,
    traceability,
)
RUN_FOLDER = re.compile(r"run-(\d+)")


def next_run_folder(results_root: Path) -> tuple[int, Path]:
    """Create the next run-N folder. An existing folder is never reused."""
    results_root.mkdir(parents=True, exist_ok=True)
    taken = [
        int(match.group(1))
        for path in results_root.iterdir()
        if (match := RUN_FOLDER.fullmatch(path.name))
    ]
    number = max(taken, default=0) + 1
    while True:
        folder = results_root / f"run-{number}"
        try:
            folder.mkdir()
        except FileExistsError:
            number += 1
            continue
        return number, folder


def execute(module: ModuleType, ctx: Context) -> GateResult:
    """Run one gate. A crash is reported as a finding, never as a silent pass."""
    try:
        return module.run(ctx)
    except Exception as error:  # report every failure mode of a gate as a finding
        crashed = GateResult(module.NAME)
        crashed.add("GATE_CRASHED", "harness", "gate completes", f"{type(error).__name__}: {error}")
        return crashed


def tool_versions(ctx: Context) -> dict[str, str]:
    versions: dict[str, str] = {"python": sys.version.split()[0]}
    for tool in ("ruff", "bandit", "pytest"):
        done = run_tool([sys.executable, "-m", tool, "--version"], ctx.root)
        text = (done.stdout or done.stderr).strip().splitlines()
        versions[tool] = text[0] if text else f"unavailable (exit {done.code})"
    return versions


def git_state(ctx: Context) -> dict[str, object]:
    git = git_exe()
    if git is None:
        return {"commit": "unknown", "working_tree_clean": None}
    head = run_tool([git, "rev-parse", "HEAD"], ctx.root)
    status = run_tool([git, "status", "--porcelain"], ctx.root)
    return {
        "commit": head.stdout.strip() or "unknown",
        "working_tree_clean": status.stdout.strip() == "" if status.code == 0 else None,
    }


def finding_dict(finding: Finding) -> dict[str, str]:
    return asdict(finding)


def clean(value: object, root: Path) -> object:
    """Sanitise every string in a JSON-like structure."""
    if isinstance(value, str):
        return sanitize(value, root)
    if isinstance(value, dict):
        return {key: clean(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [clean(item, root) for item in value]
    return value


def write_text(path: Path, text: str, root: Path) -> None:
    path.write_bytes(sanitize(text, root).encode("utf-8"))


def write_run(folder: Path, number: int, results: list[GateResult], ctx: Context) -> bool:
    """Write report.json plus the captured output of each gate. Return overall PASS."""
    passed = all(result.passed for result in results)
    report = {
        "run": number,
        "result": "PASS" if passed else "FAIL",
        "timestamp_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "baseline_tag": ctx.baseline_tag,
        "git": git_state(ctx),
        "tools": tool_versions(ctx),
        "gates": [
            {
                "gate": result.gate,
                "status": "PASS" if result.passed else "FAIL",
                "finding_count": len(result.findings),
                "findings": [finding_dict(finding) for finding in result.findings],
            }
            for result in results
        ],
    }
    text = json.dumps(clean(report, ctx.root), indent=2) + "\n"
    (folder / "report.json").write_bytes(text.encode("utf-8"))
    for result in results:
        write_text(folder / f"{result.gate}.stdout.txt", result.stdout, ctx.root)
        write_text(folder / f"{result.gate}.stderr.txt", result.stderr, ctx.root)
        for name, content in result.artifacts.items():
            write_text(folder / f"{result.gate}.{name}", content, ctx.root)
    return passed


def print_summary(number: int, results: list[GateResult], passed: bool) -> None:
    print(f"Harness run {number}")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"  {result.gate:<18} {status}  findings={len(result.findings)}")
    print(f"RESULT: {'PASS' if passed else 'FAIL'}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run all harness gates.")
    parser.add_argument("--root", type=Path, default=default_root)
    parser.add_argument("--results-dir", type=Path, default=None)
    parser.add_argument("--baseline-tag", default=BASELINE_TAG)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    ctx = Context(root=args.root.resolve(), baseline_tag=args.baseline_tag)
    results_root = args.results_dir or ctx.root / "evidence" / "gate-runs"
    number, folder = next_run_folder(results_root)
    results = [execute(module, ctx) for module in GATES]
    passed = write_run(folder, number, results, ctx)
    print_summary(number, results, passed)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
