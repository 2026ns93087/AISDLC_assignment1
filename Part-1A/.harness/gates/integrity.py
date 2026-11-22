"""Gate integrity: protected paths must equal the baseline tag (constitution VII)."""

from gates.base import Context, GateResult, git_exe, run_tool

NAME = "integrity"
REQUIREMENT = "constitution VII"
STATUS_NAMES = {"M": "modified", "D": "deleted", "A": "added", "R": "renamed", "T": "type changed"}


def protected_paths(ctx: Context) -> list[str]:
    """Paths frozen at the baseline. tasks.md is deliberately absent (checkbox ticks allowed)."""
    feature = ctx.feature_dir
    return [
        "tests",
        ".harness",
        "pyproject.toml",
        f"{feature}/spec.md",
        f"{feature}/plan.md",
        f"{feature}/data-model.md",
        f"{feature}/contracts",
    ]


def run(ctx: Context) -> GateResult:
    result = GateResult(NAME)
    git = git_exe()
    if git is None:
        result.add("GIT_MISSING", REQUIREMENT, "git found on PATH or in HARNESS_GIT", "not found")
        return result
    tag = f"refs/tags/{ctx.baseline_tag}"
    probe = run_tool([git, "rev-parse", "-q", "--verify", f"{tag}^{{commit}}"], ctx.root)
    result.stdout += probe.stdout
    result.stderr += probe.stderr
    if probe.code != 0:
        result.add(
            "BASELINE_MISSING",
            REQUIREMENT,
            f"tag {ctx.baseline_tag} exists",
            "tag not found",
        )
        return result
    paths = protected_paths(ctx)
    diff = run_tool([git, "diff", "--name-status", "--relative", tag, "--", *paths], ctx.root)
    extra = run_tool([git, "ls-files", "--others", "--exclude-standard", "--", *paths], ctx.root)
    result.stdout += diff.stdout + extra.stdout
    result.stderr += diff.stderr + extra.stderr
    if diff.code != 0 or extra.code != 0:
        result.add("TOOL_ERROR", REQUIREMENT, "git diff succeeds", f"exit {diff.code}/{extra.code}")
        return result
    for line in diff.stdout.splitlines():
        status, _, path = line.partition("\t")
        label = STATUS_NAMES.get(status[:1], status)
        result.add(
            "PROTECTED_PATH_CHANGED",
            REQUIREMENT,
            f"{path} identical to tag {ctx.baseline_tag}",
            f"{label} since the baseline",
            location=path,
        )
    for path in extra.stdout.splitlines():
        result.add(
            "PROTECTED_PATH_CHANGED",
            REQUIREMENT,
            f"no file under a protected path that is absent from tag {ctx.baseline_tag}",
            "new file not in the baseline",
            location=path,
        )
    return result
