"""Gate banned_calls: dangerous calls and suppression comments (constitution IV and VI)."""

import ast
import io
import tokenize
from pathlib import Path

from gates.base import Context, GateResult, python_files, relative

NAME = "banned_calls"
REQUIREMENT = "constitution IV, VI"
BANNED_NAMES = frozenset({"eval", "exec"})
BANNED_ATTRIBUTES = frozenset({"os.system", "os.popen"})
BANNED_MODULES = frozenset({"pickle", "cPickle", "marshal", "shelve"})
SUPPRESSIONS = ("noqa", "nosec", "type: ignore", "pylint: disable", "ruff: noqa", "fmt: off")


def dotted_name(node: ast.AST) -> str:
    """'os.system' for an attribute chain, the plain name for a Name, '' otherwise."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted_name(node.value)
        return f"{base}.{node.attr}" if base else ""
    return ""


def banned_in_tree(tree: ast.AST) -> list[tuple[str, int]]:
    """(description, line) for each banned call, import or shell=True keyword."""
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted_name(node.func)
            if name in BANNED_NAMES or name in BANNED_ATTRIBUTES:
                hits.append((f"call to {name}", node.lineno))
            for keyword in node.keywords:
                is_true = isinstance(keyword.value, ast.Constant) and keyword.value.value is True
                if keyword.arg == "shell" and is_true:
                    hits.append(("shell=True", node.lineno))
        elif isinstance(node, ast.Import):
            hits.extend(
                (f"import of {alias.name}", node.lineno)
                for alias in node.names
                if alias.name.split(".")[0] in BANNED_MODULES
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module
            and node.module.split(".")[0] in BANNED_MODULES
        ):
            hits.append((f"import from {node.module}", node.lineno))
    return hits


def suppression_comments(source: str) -> list[tuple[str, int]]:
    """(marker, line) for each comment that silences a tool. Strings are not comments."""
    hits: list[tuple[str, int]] = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError):
        return hits
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        lowered = token.string.lower()
        hits.extend((marker, token.start[0]) for marker in SUPPRESSIONS if marker in lowered)
    return hits


def scan_file(result: GateResult, ctx: Context, path: Path, check_calls: bool) -> None:
    source = path.read_text(encoding="utf-8")
    location = relative(ctx, path)
    for marker, line in suppression_comments(source):
        result.add(
            "SUPPRESSION_COMMENT",
            REQUIREMENT,
            "no comment that silences a tool",
            f"found '{marker}'",
            location=f"{location}:{line}",
        )
    if not check_calls:
        return
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as error:
        result.add(
            "SYNTAX_ERROR", REQUIREMENT, "source parses", str(error), f"{location}:{error.lineno}"
        )
        return
    for description, line in banned_in_tree(tree):
        result.add(
            "BANNED_CALL",
            REQUIREMENT,
            "no eval, exec, pickle, os.system or shell=True in shipped code",
            description,
            location=f"{location}:{line}",
        )


def run(ctx: Context) -> GateResult:
    result = GateResult(NAME)
    for path in python_files(ctx.src):
        scan_file(result, ctx, path, check_calls=True)
    for folder in (ctx.tests, ctx.harness):
        for path in python_files(folder):
            scan_file(result, ctx, path, check_calls=False)
    return result
