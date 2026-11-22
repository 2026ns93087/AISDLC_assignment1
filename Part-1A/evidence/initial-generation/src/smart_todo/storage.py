"""Storage layer: read and write the JSON store file (FR-017, FR-021, FR-022)."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from smart_todo.domain import Store, empty_store
from smart_todo.errors import AppError


def is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def check_shape(data: Any) -> Store:
    """Return the store when it has the FR-017 form, otherwise raise STORAGE_CORRUPT."""
    if not isinstance(data, dict):
        raise AppError("STORAGE_CORRUPT", "The store file must contain a JSON object.")
    for key in ("version", "next_id", "tasks"):
        if key not in data:
            raise AppError("STORAGE_CORRUPT", f"The store file has no '{key}' field.")
    if not is_plain_int(data["version"]) or data["version"] != 1:
        raise AppError("STORAGE_CORRUPT", "Unsupported store version.")
    if not is_plain_int(data["next_id"]):
        raise AppError("STORAGE_CORRUPT", "The 'next_id' field must be an integer.")
    tasks = data["tasks"]
    if not isinstance(tasks, list) or not all(isinstance(task, dict) for task in tasks):
        raise AppError("STORAGE_CORRUPT", "The 'tasks' field must be a list of objects.")
    return data


def load(path: Path) -> Store:
    """Read the store. A missing file is an empty store and is not created (FR-022)."""
    if not path.exists():
        return empty_store()
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError) as error:
        raise AppError("STORAGE_CORRUPT", "The store file cannot be read as JSON.") from error
    return check_shape(data)


def save(path: Path, store: Store) -> None:
    """Write the store atomically: temporary file in the same folder, then replace."""
    data = (json.dumps(store, indent=2) + "\n").encode("utf-8")
    replaced = False
    temporary = ""
    try:
        handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".todo-", suffix=".tmp")
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        replaced = True
    except OSError as error:
        raise AppError("STORAGE_ERROR", "The store file cannot be written.") from error
    finally:
        if temporary and not replaced:
            Path(temporary).unlink(missing_ok=True)
