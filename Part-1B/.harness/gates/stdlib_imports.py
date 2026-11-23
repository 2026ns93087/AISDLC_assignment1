"""Gate stdlib_imports: runtime code imports only the standard library (NFR-001)."""

import ast
import sys

from gates.base import Context, GateResult, python_files, relative

NAME = "stdlib_imports"
REQUIREMENT = "NFR-001"
LOCAL_PACKAGE = "reminder_agent"


def imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    """(top-level module name, line) for every absolute import in the tree."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name.split(".")[0], node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.module.split(".")[0], node.lineno))
    return found


def run(ctx: Context) -> GateResult:
    result = GateResult(NAME)
    allowed = set(sys.stdlib_module_names) | {LOCAL_PACKAGE}
    for path in python_files(ctx.src):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as error:
            result.add(
                "SYNTAX_ERROR",
                REQUIREMENT,
                "source parses",
                str(error),
                location=f"{relative(ctx, path)}:{error.lineno}",
            )
            continue
        for module, line in imported_modules(tree):
            if module not in allowed:
                result.add(
                    "NON_STDLIB_IMPORT",
                    REQUIREMENT,
                    "import from the Python standard library or the reminder_agent package",
                    f"import of {module}",
                    location=f"{relative(ctx, path)}:{line}",
                )
    return result
