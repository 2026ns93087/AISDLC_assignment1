"""Gate secret_path_scan: no secrets and no machine-specific absolute paths (NFR-007)."""

import re
from collections.abc import Iterator
from pathlib import Path

from gates.base import SKIPPED_DIRS, Context, GateResult, relative

NAME = "secret_path_scan"
REQUIREMENT = "NFR-007"
SCAN_ROOTS = ("src", "tests", ".harness", "evidence", "specs", "README.md", "pyproject.toml")
TEXT_SUFFIXES = frozenset(
    {".py", ".md", ".toml", ".json", ".txt", ".yml", ".yaml", ".cfg", ".ini", ".xml", ".log"}
)
SECRET_PATTERNS = {
    "aws-access-key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github-token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "api-key-prefix": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "private-key": re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
    "assigned-secret": re.compile(
        r"""(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b['"]?\s*[:=]\s*['"][^'"\s]{8,}['"]"""
    ),
}
PATH_PATTERNS = {
    "windows-absolute-path": re.compile(r"(?<![A-Za-z0-9\\])[A-Za-z]:[\\/][\w.$-]"),
    "unix-home-path": re.compile(r"(?<![\w.:/-])/(?:home|Users|root)/[\w.-]+"),
}


def iter_text_files(ctx: Context) -> Iterator[Path]:
    for name in SCAN_ROOTS:
        base = ctx.root / name
        if base.is_file():
            yield base
        elif base.is_dir():
            for path in sorted(base.rglob("*")):
                if (
                    path.is_file()
                    and path.suffix.lower() in TEXT_SUFFIXES
                    and not SKIPPED_DIRS.intersection(path.parts)
                ):
                    yield path


def mask(text: str) -> str:
    """Never echo a whole secret or path into the report."""
    return text[:6] + "..." if len(text) > 6 else text


def scan_line(line: str) -> list[tuple[str, str, str]]:
    """(code, pattern name, matched text) for every hit on one line."""
    hits = []
    for name, pattern in SECRET_PATTERNS.items():
        hits.extend(("SECRET_FOUND", name, m.group(0)) for m in pattern.finditer(line))
    for name, pattern in PATH_PATTERNS.items():
        hits.extend(("ABSOLUTE_PATH", name, m.group(0)) for m in pattern.finditer(line))
    return hits


def run(ctx: Context) -> GateResult:
    result = GateResult(NAME)
    for path in iter_text_files(ctx):
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            for code, name, matched in scan_line(line):
                result.add(
                    code,
                    REQUIREMENT,
                    "no secret and no machine-specific absolute path",
                    f"{name}: {mask(matched)}",
                    location=f"{relative(ctx, path)}:{number}",
                )
    return result
