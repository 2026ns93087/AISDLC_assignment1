"""Gate tests: every acceptance test passes (AC-001 to AC-047, SC-001)."""

import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from gates.base import Context, GateResult, load_ac_rows, run_tool

NAME = "tests"
AC_NAME = re.compile(r"test_ac_(\d{3})")
AC_DOC = re.compile(r"AC-(\d{3})")
MAX_TEXT = 1500


def clip(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "..."


def ac_id_for(name: str, message: str, doc: str) -> str:
    """The AC a test belongs to: from its name, otherwise from the first AC in its text."""
    match = AC_NAME.search(name) or AC_DOC.search(doc) or AC_DOC.search(message)
    return f"AC-{match.group(1)}" if match else "AC-UNKNOWN"


def split_assertion(message: str) -> tuple[str, str]:
    """Pull the 'assert ...' line out of a pytest failure as the observed condition."""
    for line in message.splitlines():
        stripped = line.strip()
        if stripped.startswith(("assert ", "AssertionError", "E ")):
            return "test assertion holds", stripped.removeprefix("E ").strip()
    first = message.strip().splitlines()[0] if message.strip() else "no message"
    return "test assertion holds", first


def run(ctx: Context) -> GateResult:
    result = GateResult(NAME)
    rows = load_ac_rows(ctx)
    with tempfile.TemporaryDirectory() as folder:
        report = Path(folder) / "junit.xml"
        command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q"]
        command += ["--tb=short", "--color=no"]
        command += [f"--junitxml={report}"]
        done = run_tool(command, ctx.root)
        result.stdout = done.stdout
        result.stderr = done.stderr
        if not report.is_file():
            result.add(
                "TOOL_ERROR",
                "SC-001",
                "pytest writes a JUnit report",
                f"exit {done.code}, no report",
                stdout=clip(done.stdout),
                stderr=clip(done.stderr),
            )
            return result
        xml_text = report.read_text(encoding="utf-8")
    result.artifacts["junit.xml"] = xml_text
    suite = ET.fromstring(xml_text)
    cases = list(suite.iter("testcase"))
    if not cases:
        result.add("NO_TESTS", "SC-001", "at least one test is collected", "0 tests ran")
    for case in cases:
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is None:
            continue
        name = case.get("name", "")
        message = problem.get("message", "") + "\n" + (problem.text or "")
        ac = ac_id_for(name, message, "")
        expected, observed = split_assertion(message)
        spec_text = rows.get(ac, ("", ""))[1]
        result.add(
            "TEST_FAILED",
            ac,
            f"{ac} holds: {clip(spec_text)}" if spec_text else expected,
            clip(observed),
            location=f"{case.get('classname', '')}::{name}",
            stdout=clip(message),
        )
    return result
