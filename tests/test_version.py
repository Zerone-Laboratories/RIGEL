"""Unit tests for the version module."""

from version import VERSION


def test_version_is_string():
    assert isinstance(VERSION, str)


def test_version_format():
    """VERSION should follow semver-like MAJOR.MINOR.PATCH format."""
    parts = VERSION.split(".")
    assert len(parts) == 3, f"Expected 3 parts, got {parts}"
    # Major and minor should be digits; patch may be 'X' for dev
    assert parts[0].isdigit()
    assert parts[1].isdigit()
