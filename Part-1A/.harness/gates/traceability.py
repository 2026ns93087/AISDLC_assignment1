"""Gate traceability: every AC in the spec is named by at least one test (NFR-006, SC-003).

The gate proves that an AC is mentioned in a test name or docstring. It cannot prove the test
asserts anything; that is the human review in task T-030.
"""

import ast
import re

from gates.base import Context, GateResult, load_ac_rows, python_files, relative

NAME = "traceability"
REQUIREMENT = "NFR-006, SC-003"
NAME_ID = re.compile(r"test_ac_(\d{3})")
TEXT_ID = re.compile(r"AC-(\d{3})")


def ids_in_source(source: str) -> set[str]:
    """AC ids named by test functions (name or docstring) in one source file."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not node.name.startswith("test_"):
            continue
        found.update(f"AC-{number}" for number in NAME_ID.findall(node.name))
        found.update(f"AC-{number}" for number in TEXT_ID.findall(ast.get_docstring(node) or ""))
    return found


def run(ctx: Context) -> GateResult:
    result = GateResult(NAME)
    rows = load_ac_rows(ctx)
    if not rows:
        result.add("SPEC_MISSING", REQUIREMENT, "AC rows found in spec.md", "no AC rows")
        return result
    covered: set[str] = set()
    for path in python_files(ctx.tests):
        try:
            covered |= ids_in_source(path.read_text(encoding="utf-8"))
        except SyntaxError as error:
            result.add(
                "SYNTAX_ERROR",
                REQUIREMENT,
                "test file parses",
                str(error),
                location=relative(ctx, path),
            )
    for ac in sorted(rows):
        if ac not in covered:
            result.add(
                "AC_WITHOUT_TEST",
                ac,
                f"a test whose name or docstring contains {ac}",
                "no test names this AC",
            )
    for ac in sorted(covered - set(rows)):
        result.add(
            "TEST_FOR_UNKNOWN_AC",
            ac,
            "every AC named in a test exists in the spec",
            f"{ac} is not in spec.md",
        )
    return result
