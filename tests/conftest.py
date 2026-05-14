"""Shared test fixtures for the RIGEL test suite."""

import os
import sys
import tempfile
import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir():
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def change_test_dir(temp_dir):
    """Change working directory to a temp dir for the duration of the test."""
    old_cwd = os.getcwd()
    os.chdir(temp_dir)
    yield temp_dir
    os.chdir(old_cwd)
