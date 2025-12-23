"""Tests for the version module."""

import pytest
from hubcap.version import (
    parse_semver_tag,
    is_valid_semver_tag,
    is_valid_stable_semver_tag,
    strip_v_from_version,
    get_existing_tags,
    get_valid_remote_tags,
    latest_version,
    VersionError,
)


class TestParseSemverTag:
    """Tests for parse_semver_tag function."""

    def test_parse_valid_semver_tag(self):
        """Test parsing a valid semver tag."""
        result = parse_semver_tag("1.2.3")
        assert result is not None
        assert result.group("major") == "1"
        assert result.group("minor") == "2"
        assert result.group("patch") == "3"

    def test_parse_semver_tag_with_v_prefix(self):
        """Test parsing semver tag with v prefix."""
        result = parse_semver_tag("v1.2.3")
        assert result is not None
        assert result.group("major") == "1"
        assert result.group("minor") == "2"
        assert result.group("patch") == "3"

    def test_parse_semver_with_prerelease(self):
        """Test parsing semver tag with prerelease."""
        result = parse_semver_tag("1.2.3-rc1")
        assert result is not None
        assert result.group("prerelease") == "rc1"

    def test_parse_semver_with_build_metadata(self):
        """Test parsing semver tag with build metadata."""
        result = parse_semver_tag("1.2.3+build.123")
        assert result is not None
        assert result.group("buildmetadata") == "build.123"

    def test_parse_semver_with_prerelease_and_build(self):
        """Test parsing semver tag with both prerelease and build metadata."""
        result = parse_semver_tag("1.2.3-alpha.1+build.1")
        assert result is not None
        assert result.group("prerelease") == "alpha.1"
        assert result.group("buildmetadata") == "build.1"

    def test_parse_invalid_semver_tag(self):
        """Test parsing an invalid semver tag."""
        result = parse_semver_tag("invalid-version")
        assert result is None

    def test_parse_none_tag(self):
        """Test parsing None as a tag."""
        result = parse_semver_tag(None)
        assert result is None

    def test_parse_non_string_tag(self):
        """Test parsing non-string tag."""
        result = parse_semver_tag(123)
        assert result is None


class TestIsValidSemverTag:
    """Tests for is_valid_semver_tag function."""

    def test_valid_simple_version(self):
        """Test validation of simple version."""
        assert is_valid_semver_tag("1.2.3") is True

    def test_valid_version_with_v_prefix(self):
        """Test validation of version with v prefix."""
        assert is_valid_semver_tag("v1.2.3") is True

    def test_valid_version_with_prerelease(self):
        """Test validation of version with prerelease."""
        assert is_valid_semver_tag("1.0.0-alpha") is True
        assert is_valid_semver_tag("1.0.0-beta") is True
        assert is_valid_semver_tag("1.0.0-rc1") is True

    def test_valid_version_with_build_metadata(self):
        """Test validation of version with build metadata."""
        assert is_valid_semver_tag("1.2.3+meta") is True
        assert is_valid_semver_tag("1.2.3+build.1") is True

    def test_invalid_version(self):
        """Test validation of invalid version."""
        assert is_valid_semver_tag("not-a-version") is False
        assert is_valid_semver_tag("v") is False
        assert is_valid_semver_tag("1.2") is False

    def test_invalid_type(self):
        """Test validation with invalid types."""
        assert is_valid_semver_tag(None) is False
        assert is_valid_semver_tag(123) is False
        assert is_valid_semver_tag([]) is False


class TestIsValidStableSemverTag:
    """Tests for is_valid_stable_semver_tag function."""

    def test_valid_stable_version(self):
        """Test validation of stable version."""
        assert is_valid_stable_semver_tag("1.2.3") is True
        assert is_valid_stable_semver_tag("v1.2.3") is True
        assert is_valid_stable_semver_tag("0.0.0") is True

    def test_invalid_prerelease_version(self):
        """Test validation rejects prerelease versions."""
        assert is_valid_stable_semver_tag("1.2.3-alpha") is False
        assert is_valid_stable_semver_tag("1.2.3-rc1") is False

    def test_invalid_version(self):
        """Test validation of invalid version."""
        assert is_valid_stable_semver_tag("not-a-version") is False

    def test_build_metadata_is_stable(self):
        """Test that build metadata alone doesn't prevent stability."""
        assert is_valid_stable_semver_tag("1.2.3+build") is True


class TestStripVFromVersion:
    """Tests for strip_v_from_version function."""

    def test_strip_v_prefix(self):
        """Test stripping v prefix from version."""
        assert strip_v_from_version("v1.2.3") == "1.2.3"

    def test_no_v_prefix(self):
        """Test version without v prefix."""
        assert strip_v_from_version("1.2.3") == "1.2.3"

    def test_multiple_v_prefix(self):
        """Test only first v is stripped."""
        assert strip_v_from_version("vv1.2.3") == "v1.2.3"

    def test_invalid_type(self):
        """Test invalid type raises error."""
        with pytest.raises(VersionError):
            strip_v_from_version(123)

    def test_with_prerelease(self):
        """Test stripping v from prerelease version."""
        assert strip_v_from_version("v1.2.3-alpha") == "1.2.3-alpha"


class TestGetExistingTags:
    """Tests for get_existing_tags function."""

    def test_filter_valid_tags(self):
        """Test filtering valid semver tags."""
        tags = ["1.0.0", "1.0.1", "invalid-tag", "2.0.0"]
        result = get_existing_tags(tags)
        assert result == {"1.0.0", "1.0.1", "2.0.0"}

    def test_empty_list(self):
        """Test with empty list."""
        result = get_existing_tags([])
        assert result == set()

    def test_all_invalid_tags(self):
        """Test with all invalid tags."""
        tags = ["invalid-1", "not-semver", "just-text"]
        result = get_existing_tags(tags)
        assert result == set()

    def test_with_invalid_type(self):
        """Test with invalid type like dict."""
        result = get_existing_tags({"key": "value"})
        assert result == set()

    def test_with_v_prefix(self):
        """Test filtering tags with v prefix."""
        tags = ["v1.0.0", "v1.0.1", "invalid"]
        result = get_existing_tags(tags)
        assert result == {"v1.0.0", "v1.0.1"}

    def test_with_set_input(self):
        """Test with set input."""
        tags = {"1.0.0", "1.0.1", "invalid"}
        result = get_existing_tags(tags)
        assert result == {"1.0.0", "1.0.1"}

    def test_invalid_type(self):
        """Test with invalid input type."""
        result = get_existing_tags("not-a-list")
        assert result == set()

    def test_with_none(self):
        """Test with None input."""
        result = get_existing_tags(None)
        assert result == set()


class TestGetValidRemoteTags:
    """Tests for get_valid_remote_tags function."""

    def test_get_valid_tags(self, mock_repo):
        """Test getting valid remote tags."""
        mock_repo.git.tag.return_value = "1.0.0\n1.0.1\ninvalid-tag\n2.0.0"
        result = get_valid_remote_tags(mock_repo)
        assert result == {"1.0.0", "1.0.1", "2.0.0"}

    def test_empty_tags(self, mock_repo):
        """Test with no tags."""
        mock_repo.git.tag.return_value = ""
        result = get_valid_remote_tags(mock_repo)
        assert result == set()

    def test_all_invalid_tags(self, mock_repo):
        """Test with all invalid tags."""
        mock_repo.git.tag.return_value = "invalid-1\ninvalid-2"
        result = get_valid_remote_tags(mock_repo)
        assert result == set()

    def test_with_v_prefix(self, mock_repo):
        """Test with v-prefixed tags."""
        mock_repo.git.tag.return_value = "v1.0.0\nv1.0.1\nv2.0.0"
        result = get_valid_remote_tags(mock_repo)
        assert result == {"v1.0.0", "v1.0.1", "v2.0.0"}

    def test_fetch_is_called(self, mock_repo):
        """Test that git fetch is called."""
        mock_repo.git.tag.return_value = "1.0.0"
        get_valid_remote_tags(mock_repo)
        mock_repo.git.fetch.assert_called_once()

    def test_none_repo(self):
        """Test with None repo."""
        result = get_valid_remote_tags(None)
        assert result == set()


class TestLatestVersion:
    """Tests for latest_version function."""

    def test_latest_final_version(self):
        """Test getting latest final version."""
        tags = ["1.0.0", "1.0.1", "1.0.2"]
        assert latest_version(tags) == "1.0.2"

    def test_final_beats_prerelease(self):
        """Test that final version beats prerelease."""
        tags = ["1.0.0", "1.0.1", "1.0.2-rc1"]
        assert latest_version(tags) == "1.0.1"

    def test_multiple_prerelease_versions(self):
        """Test with multiple prerelease versions."""
        tags = ["1.0.0-alpha", "1.0.0-beta", "1.0.0-rc1"]
        assert latest_version(tags) == "1.0.0-rc1"

    def test_with_v_prefix(self):
        """Test with v-prefixed versions."""
        tags = ["v1.0.0", "v1.0.1", "v1.0.2"]
        result = latest_version(tags)
        assert result in ["1.0.2", "v1.0.2"]

    def test_empty_list(self):
        """Test with empty list."""
        with pytest.raises(VersionError):
            latest_version([])

    def test_all_invalid_tags(self):
        """Test with all invalid tags."""
        with pytest.raises(VersionError):
            latest_version(["invalid-1", "not-semver"])

    def test_mixed_valid_invalid(self):
        """Test with mix of valid and invalid tags."""
        tags = ["invalid", "1.0.0", "not-valid", "1.0.1"]
        assert latest_version(tags) == "1.0.1"

    def test_single_version(self):
        """Test with single version."""
        assert latest_version(["1.0.0"]) == "1.0.0"

    def test_major_version_difference(self):
        """Test with different major versions."""
        tags = ["1.0.0", "2.0.0", "3.0.0"]
        assert latest_version(tags) == "3.0.0"

    def test_none_input(self):
        """Test with None input."""
        with pytest.raises(VersionError):
            latest_version(None)

    def test_complex_prerelease_ordering(self):
        """Test complex prerelease version ordering."""
        tags = ["1.0.0", "1.0.1-rc1", "1.0.1-rc2", "1.0.1-rc3"]
        assert latest_version(tags) == "1.0.0"

    def test_latest_with_complex_metadata(self):
        """Test latest version with complex metadata and prerelease."""
        tags = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta", "1.0.0"]
        assert latest_version(tags) == "1.0.0"

    def test_latest_preserves_prerelease_when_no_final(self):
        """Test that latest prerelease is returned when no final version exists."""
        tags = ["1.0.0-alpha", "1.0.0-beta", "1.0.0-rc1", "1.0.0-rc2"]
        result = latest_version(tags)
        assert "rc" in result

    def test_latest_with_empty_list(self):
        """Test with empty list of tags."""
        with pytest.raises(VersionError, match="No tags provided"):
            latest_version([])

    def test_latest_with_invalid_version_tags(self):
        """Test with tags that cannot be parsed as versions."""
        tags = ["not-a-version", "also-not", "invalid"]
        with pytest.raises(VersionError, match="No valid semver tags found"):
            latest_version(tags)

    def test_latest_with_mixed_valid_invalid(self):
        """Test with mix of valid and invalid semver tags."""
        tags = ["1.0.0", "not-valid", "2.0.0", "invalid", "1.5.0"]
        result = latest_version(tags)
        assert result == "2.0.0"
