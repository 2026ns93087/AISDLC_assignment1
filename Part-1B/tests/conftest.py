"""Pytest fixtures for the Reminder Agent acceptance tests."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from support import FakeModel, Sandbox, start_fake


@pytest.fixture
def fake() -> Iterator[FakeModel]:
    """A local fake model server, stopped after the test."""
    server = start_fake()
    yield server
    server.stop()


@pytest.fixture
def box(tmp_path: Path, fake: FakeModel) -> Sandbox:
    """A fresh working directory wired to the fake model."""
    return Sandbox(tmp_path / "box", fake)
