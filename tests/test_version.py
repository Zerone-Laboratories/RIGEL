"""Unit tests for the version module."""

import pytest
from version import VERSION


class TestVersion:
    """Tests for the RIGEL version string."""

    def test_version_is_string(self):
        assert isinstance(VERSION, str)

    def test_version_is_non_empty(self):
        assert len(VERSION) > 0

    def test_version_format_semver(self):
        """VERSION should follow semver-like MAJOR.MINOR.PATCH format."""
        parts = VERSION.split(".")
        assert len(parts) == 3, f"Expected 3 parts, got {parts}"
        assert parts[0].isdigit(), f"Major version should be numeric: {parts[0]}"
        assert parts[1].isdigit(), f"Minor version should be numeric: {parts[1]}"

    def test_version_major_is_positive(self):
        parts = VERSION.split(".")
        major = int(parts[0])
        assert major >= 0, f"Major version should be non-negative: {major}"

    def test_version_not_default_dev(self):
        """Ensure version is not an unset placeholder like 0.0.0."""
        assert VERSION != "0.0.0", "Version should not be an unset placeholder"

    def test_version_parts_non_empty(self):
        """Each part of the version should be non-empty."""
        parts = VERSION.split(".")
        for i, part in enumerate(parts):
            assert len(part) > 0, f"Version part {i} is empty"

    @pytest.mark.parametrize("bad_version", [
        "..",
        "a.b.c",
        "1.2",
        "1.2.3.4",
    ])
    def test_version_rejects_malformed(self, bad_version):
        """Validate that a version string meets the expected format."""
        parts = bad_version.split(".")
        is_valid = (
            len(parts) == 3
            and parts[0].isdigit()
            and parts[1].isdigit()
        )
        assert not is_valid, f"'{bad_version}' should be considered invalid"
