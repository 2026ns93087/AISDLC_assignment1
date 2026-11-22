"""Shared types and helpers for the harness gates.

The harness never imports the implementation under test. Gates read files, run external
tools in subprocesses and report findings in one common shape.
"""

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

FEATURE_DIR = "specs/001-smart-todo-cli"
BASELINE_TAG = "baseline-1A-before-implement"
AC_ROW = re.compile(r"^\| (AC-\d{3}) \| ([^|]*) \| (.*) \|\s*$", re.MULTILINE)
SKIPPED_DIRS = frozenset({"__pycache__", ".venv", ".git", ".pytest_cache", ".ruff_cache"})


@dataclass(frozen=True)
class Context:
    """Where the project under test lives and which baseline it is compared with."""

    root: Path
    baseline_tag: str = BASELINE_TAG
    feature_dir: str = FEATURE_DIR

    @property
    def src(self) -> Path:
        return self.root / "src"

    @property
    def tests(self) -> Path:
        return self.root / "tests"

    @property
    def harness(self) -> Path:
        return self.root / ".harness"

    @property
    def pyproject(self) -> Path:
        return self.root / "pyproject.toml"

    @property
    def spec(self) -> Path:
        return self.root / self.feature_dir / "spec.md"


@dataclass
class Finding:
    """One problem found by a gate (constitution, Development Workflow 3)."""

    code: str
    gate: str
    requirement: str
    expected: str
    observed: str
    location: str = ""
    stdout: str = ""
    stderr: str = ""


@dataclass
class GateResult:
    """Outcome of one gate: findings plus everything the gate captured."""

    gate: str
    findings: list[Finding] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    artifacts: dict[str, str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.findings

    def add(
        self,
        code: str,
        requirement: str,
        expected: str,
        observed: str,
        location: str = "",
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        self.findings.append(
            Finding(code, self.gate, requirement, expected, observed, location, stdout, stderr)
        )


@dataclass(frozen=True)
class ToolOutput:
    """Exit code and decoded output of an external tool."""

    code: int
    stdout: str
    stderr: str


def decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def run_tool(
    args: list[str],
    cwd: Path,
    env_extra: dict[str, str] | None = None,
    timeout: int = 600,
) -> ToolOutput:
    """Run a tool without a shell, never writing bytecode, and capture its output."""
    env = dict(os.environ)
    env.pop("FORCE_COLOR", None)
    env["NO_COLOR"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.update(env_extra or {})
    try:
        done = subprocess.run(
            args, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False
        )
    except FileNotFoundError as error:
        return ToolOutput(127, "", str(error))
    except subprocess.TimeoutExpired:
        return ToolOutput(124, "", f"timed out after {timeout} s: {' '.join(args[:4])}")
    return ToolOutput(done.returncode, decode(done.stdout), decode(done.stderr))


def git_exe() -> str | None:
    """Locate git: HARNESS_GIT, then PATH, then the default Git for Windows folder."""
    configured = os.environ.get("HARNESS_GIT") or shutil.which("git")
    if configured:
        return configured
    program_files = os.environ.get("PROGRAMFILES")
    if program_files:
        candidate = Path(program_files) / "Git" / "bin" / "git.exe"
        if candidate.is_file():
            return str(candidate)
    return None


ABSOLUTE_WINDOWS = re.compile(r"[A-Za-z]:[\\/][^\s\"'<>|]*")
ABSOLUTE_UNIX = re.compile(r"/(?:home|Users|root)/[^\s\"']*")


def prefix_pattern(path_text: str, minimum: int) -> str:
    """Regex matching path_text or any prefix of it that is at least `minimum` characters.

    Tools such as pytest cut long paths short, so a truncated copy of the project path must
    be recognised too. The tail is built as nested optional groups.
    """
    head, tail = re.escape(path_text[:minimum]), path_text[minimum:]
    nested = ""
    for char in reversed(tail):
        nested = f"(?:{re.escape(char)}{nested})?"
    return head + nested


def sanitize(text: str, root: Path) -> str:
    """Replace machine-specific paths so evidence files stay portable (NFR-007)."""
    resolved = root.resolve()
    home = Path.home()
    out = text
    for convert in (str, Path.as_posix, lambda p: str(p).replace("\\", "\\\\")):
        form, home_form = convert(resolved), convert(home)
        under_home = form.lower().startswith(home_form.lower())
        minimum = len(home_form) + 2 if under_home else len(form)
        out = re.sub(prefix_pattern(form, min(len(form), minimum)), "<root>", out, flags=re.I)
    known = [
        (Path(sys.prefix), "<venv>"),
        (Path(sys.base_prefix), "<python>"),
        (Path.home(), "<home>"),
    ]
    known.sort(key=lambda item: len(str(item[0])), reverse=True)
    for path, label in known:
        forms = {str(path), path.as_posix(), str(path).replace("\\", "\\\\")}
        pattern = re.compile("|".join(re.escape(form) for form in forms), re.IGNORECASE)
        out = pattern.sub(label, out)
    out = ABSOLUTE_WINDOWS.sub("<abs-path>", out)
    return ABSOLUTE_UNIX.sub("<abs-path>", out)


def python_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.rglob("*.py")
        if not SKIPPED_DIRS.intersection(path.parts)
    )


def relative(ctx: Context, path: str | Path) -> str:
    """Path relative to the project root, with forward slashes, when possible."""
    try:
        return Path(path).resolve().relative_to(ctx.root.resolve()).as_posix()
    except (ValueError, OSError):
        return str(path)


def load_ac_rows(ctx: Context) -> dict[str, tuple[str, str]]:
    """Acceptance criteria from the spec table: id -> (covers, given/when/then text)."""
    if not ctx.spec.is_file():
        return {}
    text = ctx.spec.read_text(encoding="utf-8")
    return {
        match.group(1): (match.group(2).strip(), match.group(3).strip())
        for match in AC_ROW.finditer(text)
    }
