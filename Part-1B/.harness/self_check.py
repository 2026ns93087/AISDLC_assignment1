"""Show that every gate can fail (task T-029).

A small throwaway project is built in a temporary folder. It passes every gate. For each gate
one or more copies of it are broken on purpose, and the gate must reject the broken copy with
the expected finding code. Broken strings are assembled at run time so this file never contains
a secret, a banned call or a suppression comment itself.

Usage: python .harness/self_check.py      (exit 0 only when every check behaves as required)
"""

import shutil
import stat
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
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
from gates.base import BASELINE_TAG, Context, git_exe, run_tool
from run_harness import GATES, execute

Mutation = Callable[[Path, str], None]

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
SPEC = "specs/001-reminder-agent/spec.md"

GOOD_FILES = {
    "src/reminder_agent/__init__.py": '"""Fixture package."""\n',
    "src/reminder_agent/core.py": '''"""Fixture module."""


def add(first: int, second: int) -> int:
    """Return the sum."""
    return first + second
''',
    "tests/test_ok.py": '''"""Fixture tests."""


def test_ac_001_passes() -> None:
    """AC-001 holds."""
    assert 1 + 1 == 2


def test_ac_002_passes() -> None:
    """AC-002 holds."""
    assert "a".upper() == "A"
''',
    SPEC: """# Fixture specification

| ID | Covers | Given / When / Then |
|----|--------|---------------------|
| AC-001 | FR-001 | first |
| AC-002 | FR-002 | second |
""",
}


@dataclass(frozen=True)
class Case:
    """One deliberately broken input and the finding the gate must report for it."""

    gate: ModuleType
    label: str
    mutate: Mutation
    expected_code: str
    expected_requirement: str = ""


def write(root: Path, relative_path: str, text: str) -> None:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))


def git(root: Path, exe: str, *args: str) -> None:
    command = [exe, "-c", "user.name=harness", "-c", "user.email=harness@example.invalid"]
    command += ["-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args]
    done = run_tool(command, root)
    if done.code != 0:
        message = f"git {' '.join(args)} failed: {done.stderr.strip()}"
        raise RuntimeError(message)


def build_project(root: Path, exe: str) -> None:
    """A project that passes every gate, committed and tagged as the baseline."""
    write(root, "pyproject.toml", PYPROJECT.read_text(encoding="utf-8"))
    for relative_path, text in GOOD_FILES.items():
        write(root, relative_path, text)
    git(root, exe, "init", "-q")
    git(root, exe, "add", "-A")
    git(root, exe, "commit", "-q", "-m", "fixture baseline")
    git(root, exe, "tag", BASELINE_TAG)


def force_remove(path: Path) -> None:
    """Delete a folder that contains read-only git objects (Windows)."""
    for item in path.rglob("*"):
        try:
            item.chmod(stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            continue
    shutil.rmtree(path, ignore_errors=True)


def adding(relative_path: str, text: str) -> Mutation:
    def mutate(root: Path, _exe: str) -> None:
        write(root, relative_path, text)

    return mutate


def modify_protected_file(root: Path, _exe: str) -> None:
    path = root / "tests" / "test_ok.py"
    path.write_bytes(path.read_bytes() + b"\n# edited after the baseline\n")


def delete_baseline_tag(root: Path, exe: str) -> None:
    git(root, exe, "tag", "-d", BASELINE_TAG)


def add_ac_without_test(root: Path, _exe: str) -> None:
    path = root / SPEC
    path.write_bytes(path.read_bytes() + b"| AC-003 | FR-003 | third, no test |\n")


def build_cases() -> list[Case]:
    leaked_key = 'KEY = "' + "AKIA" + "ABCDEFGHIJKLMNOP" + '"\n'
    machine_path = 'LOCATION = "' + "C:" + "/" + "Users" + '/someone/data"\n'
    banned = "RESULT = " + "ev" + "al" + '("1 + 1")\n'
    silenced = "VALUE = 1  # " + "no" + "qa" + "\n"
    shell_code = (
        "import subprocess\n\n\ndef run() -> None:\n"
        '    subprocess.run(["echo", "x"], check=False)\n'
    )
    failing_test = (
        "def test_ac_001_fails() -> None:\n"
        '    """AC-001 is broken on purpose."""\n'
        "    assert 1 == 2\n"
    )
    return [
        Case(integrity, "protected test file changed", modify_protected_file,
             "PROTECTED_PATH_CHANGED"),
        Case(integrity, "baseline tag missing", delete_baseline_tag, "BASELINE_MISSING"),
        Case(secret_path_scan, "key-like string in source",
             adding("src/reminder_agent/leak.py", leaked_key), "SECRET_FOUND"),
        Case(secret_path_scan, "machine-specific absolute path",
             adding("src/reminder_agent/where.py", machine_path), "ABSOLUTE_PATH"),
        Case(stdlib_imports, "third-party import in src",
             adding("src/reminder_agent/extra.py", "import requests\n"), "NON_STDLIB_IMPORT"),
        Case(banned_calls, "dynamic code execution call in src",
             adding("src/reminder_agent/dynamic.py", banned), "BANNED_CALL"),
        Case(banned_calls, "tool-silencing comment in src",
             adding("src/reminder_agent/silenced.py", silenced), "SUPPRESSION_COMMENT"),
        Case(ruff_gate, "unused import in src",
             adding("src/reminder_agent/unused.py", "import os\n"), "RUFF_F401"),
        Case(bandit_gate, "subprocess use in src",
             adding("src/reminder_agent/shell.py", shell_code), "BANDIT_B404"),
        Case(tests_gate, "failing acceptance test",
             adding("tests/test_bad.py", failing_test), "TEST_FAILED", "AC-001"),
        Case(traceability, "AC row in spec with no test", add_ac_without_test,
             "AC_WITHOUT_TEST", "AC-003"),
    ]


def run_case(case: Case, exe: str) -> tuple[bool, str]:
    """Break a fresh copy of the project and run one gate. Returns (rejected correctly, codes)."""
    root = Path(tempfile.mkdtemp(prefix="harness-self-check-"))
    try:
        build_project(root, exe)
        case.mutate(root, exe)
        result = execute(case.gate, Context(root=root))
    finally:
        force_remove(root)
    codes = sorted({finding.code for finding in result.findings})
    matched = [
        finding
        for finding in result.findings
        if finding.code == case.expected_code
        and (not case.expected_requirement or finding.requirement == case.expected_requirement)
    ]
    shown = ", ".join(codes[:3]) + (" ..." if len(codes) > 3 else "")
    return bool(matched), shown or "no findings"


def run_good_project(exe: str) -> list[tuple[str, bool, int]]:
    """Run every gate on the unbroken project. Each must pass."""
    root = Path(tempfile.mkdtemp(prefix="harness-self-check-"))
    try:
        build_project(root, exe)
        ctx = Context(root=root)
        outcomes = []
        for module in GATES:
            result = execute(module, ctx)
            outcomes.append((module.NAME, result.passed, len(result.findings)))
    finally:
        force_remove(root)
    return outcomes


def main() -> int:
    exe = git_exe()
    if exe is None:
        print("self-check cannot run: git was not found (set HARNESS_GIT)")
        return 2
    print("Broken inputs: each gate must reject its own broken copy")
    print(f"{'gate':<18} {'broken input':<38} {'expected finding':<24} observed / verdict")
    bad_ok = 0
    cases = build_cases()
    for case in cases:
        rejected, observed = run_case(case, exe)
        bad_ok += rejected
        verdict = "REJECTED" if rejected else "NOT REJECTED (gate is broken)"
        print(f"{case.gate.NAME:<18} {case.label:<38} {case.expected_code:<24} "
              f"{observed} -> {verdict}")
    print()
    print("Good input: every gate must accept the unbroken project")
    good = run_good_project(exe)
    for name, passed, count in good:
        print(f"{name:<18} {'PASS' if passed else 'FAIL'}  findings={count}")
    good_ok = sum(1 for _, passed, _ in good if passed)
    gates_covered = len({case.gate.NAME for case in cases})
    print()
    print(f"Broken inputs rejected: {bad_ok} of {len(cases)} (covering {gates_covered} gates)")
    print(f"Good input accepted by: {good_ok} of {len(good)} gates")
    everything = bad_ok == len(cases) and good_ok == len(good) and gates_covered == len(GATES)
    print(f"SELF-CHECK: {'PASS' if everything else 'FAIL'}")
    return 0 if everything else 1


if __name__ == "__main__":
    sys.exit(main())
