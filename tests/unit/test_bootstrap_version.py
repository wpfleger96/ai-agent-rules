"""Tests for version utilities."""

import pytest

from packaging.version import InvalidVersion

from ai_rules.bootstrap.version import is_newer, parse_version


@pytest.mark.unit
@pytest.mark.bootstrap
class TestParseVersion:
    def test_parse_version_invalid_raises_error(self):
        with pytest.raises(InvalidVersion):
            parse_version("not.a.version")


@pytest.mark.unit
@pytest.mark.bootstrap
class TestIsNewer:
    @pytest.mark.parametrize(
        "latest,current,expected",
        [
            # Basic version comparisons
            ("1.2.0", "1.1.0", True),  # newer minor
            ("1.1.0", "1.2.0", False),  # older
            ("1.2.0", "1.2.0", False),  # same
            ("2.0.0", "1.9.9", True),  # major bump
            ("1.3.0", "1.2.9", True),  # minor bump
            ("1.2.4", "1.2.3", True),  # patch bump
            # Version prefix variations
            ("v1.2.0", "v1.1.0", True),  # both with v prefix
            ("v1.2.0", "1.1.0", True),  # only latest with v prefix
            ("1.2.0", "v1.1.0", True),  # only current with v prefix
        ],
    )
    def test_version_comparison(self, latest, current, expected):
        assert is_newer(latest, current) is expected

    @pytest.mark.parametrize(
        "latest,current,expected",
        [
            ("1.2.0", "1.2.0-alpha.1", True),  # release > prerelease
            ("1.2.0-beta.1", "1.2.0-alpha.1", True),  # beta > alpha
        ],
    )
    def test_prerelease_versions(self, latest, current, expected):
        assert is_newer(latest, current) is expected

    @pytest.mark.parametrize(
        "latest,current",
        [
            ("invalid", "1.2.0"),
            ("1.2.0", "invalid"),
            ("invalid", "also-invalid"),
        ],
    )
    def test_invalid_versions_return_false(self, latest, current):
        assert is_newer(latest, current) is False
