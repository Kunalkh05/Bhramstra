"""
Shared test fixtures for BRAHMASTRA test suite.
"""

import pytest
from typer.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Fixture providing a clean CLI runner."""
    return CliRunner()
