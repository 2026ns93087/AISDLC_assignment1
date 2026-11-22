# Research Notes: Smart Todo CLI

**Date**: 2026-11-22 | **Plan**: [plan.md](plan.md)

No `[NEEDS CLARIFICATION]` items remain in the specification, so this phase records technical
findings that shape the plan.

## R-1 argparse and the error contract

- **Finding**: `argparse.ArgumentParser.error()` prints usage text to stderr and exits with code 2.
  Exit code 2 matches FR-019, but the text is not the JSON object FR-018 requires.
- **Decision**: subclass the parser, override `error(message)` to raise `AppError` with the
  `USAGE_ERROR` code and exit 2; the CLI entry point prints the JSON. Set `add_help=False` so
  `-h` cannot print text to stdout (the spec defines no help output).
- **Alternative rejected**: hand-written parser, because it adds code without adding behaviour.

## R-2 Identifiers that look like options

- **Finding**: `todo show -1` can be mistaken for an option by argparse.
- **Decision**: use `parse_args` with the identifier as a plain string positional and validate it
  with a regular expression (PD-7). Cases covered by AC-016: `abc`, `0`, `-1`, `1.5`.
- **Open point for the tasks step**: confirm `-1` reaches the validator rather than raising a
  generic "unrecognised arguments" usage error. Either way the exit code is 2, but the error code
  must be `INVALID_ID` (AC-016). If argparse intercepts it, the CLI inserts `--` before the
  positional.

## R-3 Atomic writes

- **Finding**: `os.replace` is atomic on POSIX and on Windows within one volume.
- **Decision**: `tempfile.mkstemp(dir=<store directory>)`, write, flush, `os.fsync`, close,
  `os.replace`; delete the temp file in a `finally` if replace did not happen. AC-042 checks that
  the directory contains only the store file afterwards.

## R-4 Byte-for-byte determinism

- **Finding**: Python text mode on Windows converts `\n` to `\r\n`.
- **Decision**: write the store through a binary handle with UTF-8 bytes. Fixed key order comes
  from building dictionaries in the data-model order. Stdout and stderr write with
  `sys.stdout.write(text + "\n")`; the test helper compares decoded text with newlines normalised
  only at the final `\n`.

## R-5 Clock

- **Finding**: `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` gives the required
  format and truncates to seconds.
- **Decision**: `TODO_NOW` is validated with `re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", v)`
  plus a `datetime.strptime` round trip so `2026-13-45T99:99:99Z` is rejected as `INVALID_CLOCK`.

## R-6 Tool scope and suppression

- **Finding**: Bandit rule B101 (`assert`) and B404/B603 (`subprocess`) would fire on pytest tests
  and on the harness runner. Constitution IV forbids silencing tools.
- **Decision**: PD-4. Bandit scans shipped code (`src/`) only. This limitation is disclosed in the
  harness log and README. A banned-call scan over `src/` covers the specific risks in
  constitution VI.

## R-7 Ruff scope

- **Finding**: the Spec Kit scaffold ships `.specify/scripts/powershell/markdown_sections.py`, which
  is not project code.
- **Decision**: always run Ruff with explicit paths `src tests .harness`.

## R-8 Tool installation risk

- **Finding**: installing `specify-cli` failed on this machine because a `cryptography` wheel had to
  be built from source (Windows ARM64, Python 3.15). The fix was `uv tool install ... --python 3.13
  --system-certs --no-build-package cryptography`.
- **Decision**: the first harness task verifies that `pytest`, `ruff` and `bandit` install; if not,
  use the same approach and record the interpreter in the README setup note.
