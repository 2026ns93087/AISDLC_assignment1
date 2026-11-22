"""Pytest fixtures for the Smart Todo acceptance tests."""

from pathlib import Path

import pytest
from support import Cli


@pytest.fixture
def cli(tmp_path: Path) -> Cli:
    """A fresh sandbox (own store directory, own working directory) for each test."""
    return Cli(tmp_path / "cli")
