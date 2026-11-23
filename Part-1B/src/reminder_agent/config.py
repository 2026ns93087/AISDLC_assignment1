"""Configuration: `.env` reading, settings, API-base check and secret redaction (FR-014 to FR-018).

The API key is only ever held in `Settings.api_key`. It is removed from every message that leaves
the program (`redact`), and it is sent only to the Gemini host or to a loopback address (GR-006).
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from reminder_agent.errors import AppError

DEFAULT_MODEL = "gemini-flash-latest"
DEFAULT_BASE = "https://generativelanguage.googleapis.com"
GEMINI_HOST = "generativelanguage.googleapis.com"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
DEFAULT_TIMEOUT = 60.0
DEFAULT_DELAY = 5.0
PROJECT_ROOT = Path(__file__).resolve().parents[2]
NAME_LINE = re.compile(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)")
KEY_PATTERN = re.compile(r"[A-Za-z0-9_-]{8,256}")
MODEL_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,64}")
REDACTED = "<redacted>"


@dataclass(frozen=True)
class Target:
    """Where requests go: scheme, host, port and the path prefix of the API base."""

    scheme: str
    host: str
    port: int


@dataclass(frozen=True)
class Settings:
    """Everything the model client needs. `api_key` must never be printed or written."""

    api_key: str
    model: str
    target: Target
    timeout: float
    delay: float


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_env_text(text: str) -> dict[str, str]:
    """Parse `NAME=VALUE` lines. Blank lines and `#` comments are ignored (FR-017)."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = NAME_LINE.fullmatch(line)
        if match is not None:
            values[match.group(1)] = strip_quotes(match.group(2).strip())
    return values


def read_env_file(path: Path) -> dict[str, str]:
    """The values of one `.env` file; a missing file gives no values."""
    try:
        if not path.is_file():
            return {}
        return parse_env_text(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError) as error:
        raise AppError("INVALID_CONFIG", "The .env file cannot be read.", 3) from error


def env_file_values(environ: Mapping[str, str], cwd: Path) -> dict[str, str]:
    """Values from the `.env` file that FR-017 selects."""
    chosen = environ.get("REMINDER_AGENT_ENV_FILE", "").strip()
    if chosen:
        return read_env_file(Path(chosen))
    values = read_env_file(PROJECT_ROOT / ".env")
    values.update(read_env_file(cwd / ".env"))
    return values


def merged_environment(environ: Mapping[str, str], cwd: Path) -> dict[str, str]:
    """File values overridden by the process environment. An empty value counts as not set."""
    merged = env_file_values(environ, cwd)
    for name, value in environ.items():
        if value.strip():
            merged[name] = value
    return {name: value for name, value in merged.items() if value.strip()}


def parse_target(base: str) -> Target:
    """Check the API base (FR-014): the Gemini host over https, or a loopback address over http."""
    message = "The API base must be the Gemini host over https or a loopback address."
    try:
        parts = urlsplit(base.strip())
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError as error:
        raise AppError("INVALID_API_BASE", message, 3) from error
    clean = not parts.username and not parts.password and parts.path in ("", "/")
    clean = clean and not parts.query and not parts.fragment
    if clean and parts.scheme == "https" and host == GEMINI_HOST:
        return Target("https", host, port or 443)
    if clean and parts.scheme == "http" and host in LOOPBACK_HOSTS and port is not None:
        return Target("http", host, port)
    raise AppError("INVALID_API_BASE", message, 3)


def number_setting(environ: Mapping[str, str], name: str, default: float, low: float) -> float:
    """A numeric setting in a fixed range (FR-015, FR-016)."""
    raw = environ.get(name)
    if raw is None:
        return default
    high = 600.0 if name == "REMINDER_AGENT_TIMEOUT" else 60.0
    try:
        value = float(raw)
    except ValueError as error:
        raise AppError("INVALID_CONFIG", f"{name} must be a number.", 3) from error
    if not low <= value <= high:
        raise AppError("INVALID_CONFIG", f"{name} must be between {low:g} and {high:g}.", 3)
    return value


def validate_model(name: str) -> str:
    if MODEL_PATTERN.fullmatch(name) is None:
        raise AppError("INVALID_MODEL", "The model name has invalid characters or length.")
    return name


def build_settings(environ: Mapping[str, str], model: str) -> Settings:
    """Settings from the merged environment, checked in the order of the specification."""
    key = environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise AppError("MISSING_API_KEY", "GEMINI_API_KEY is not set (environment or .env).", 3)
    target = parse_target(environ.get("REMINDER_AGENT_API_BASE", DEFAULT_BASE))
    if KEY_PATTERN.fullmatch(key) is None:
        raise AppError("INVALID_CONFIG", "GEMINI_API_KEY has an unexpected shape.", 3)
    timeout = number_setting(environ, "REMINDER_AGENT_TIMEOUT", DEFAULT_TIMEOUT, 1.0)
    delay = number_setting(environ, "REMINDER_AGENT_RETRY_DELAY", DEFAULT_DELAY, 0.0)
    return Settings(key, model, target, timeout, delay)


def redact(text: str, key: str) -> str:
    """Remove the key from text that is about to be shown or written (GR-006)."""
    return text.replace(key, REDACTED) if key else text


def process_environment() -> Mapping[str, str]:
    return os.environ
