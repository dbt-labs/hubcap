"""Tests for the helper module."""

import json
import os
import pytest

from hubcap import helper


class TestBuildConfig:
    """Tests for build_config function."""

    def test_build_config_from_env(self, mock_config_env, mock_config):
        """Test loading config from environment variable."""
        config = helper.build_config()
        assert config == mock_config

    def test_build_config_missing_env(self, monkeypatch):
        """Test error when CONFIG environment variable is missing."""
        monkeypatch.delenv("CONFIG", raising=False)
        with pytest.raises(helper.ConfigurationError) as exc_info:
            helper.build_config()
        assert "CONFIG environment variable is not set" in str(exc_info.value)

    def test_build_config_invalid_json(self, monkeypatch):
        """Test error when CONFIG contains invalid JSON."""
        monkeypatch.setenv("CONFIG", "{invalid json}")
        with pytest.raises(helper.ConfigurationError) as exc_info:
            helper.build_config()
        assert "Invalid JSON" in str(exc_info.value)

    def test_build_config_not_dict(self, monkeypatch):
        """Test error when CONFIG is not a JSON object."""
        monkeypatch.setenv("CONFIG", '["array", "not", "dict"]')
        with pytest.raises(helper.ConfigurationError) as exc_info:
            helper.build_config()
        assert "must be a valid JSON object" in str(exc_info.value)

    def test_build_config_with_defaults(self, monkeypatch):
        """Test config with minimal required fields."""
        config = {"user": {"token": "test"}}
        monkeypatch.setenv("CONFIG", json.dumps(config))
        result = helper.build_config()
        assert result == config


class TestChangeDirectory:
    """Tests for change_directory context manager."""

    def test_change_directory_success(self, temp_dir):
        """Test changing directory temporarily."""
        original_dir = os.getcwd()
        test_dir = temp_dir / "subdir"
        test_dir.mkdir()

        try:
            with helper.change_directory(str(test_dir)):
                # On macOS, /var/folders can be symlinked to /private/var/folders
                assert str(os.getcwd()).endswith(str(test_dir).split("/")[-1])
            # Should return to original directory
            assert os.getcwd() == original_dir
        finally:
            os.chdir(original_dir)

    def test_change_directory_nonexistent(self):
        """Test changing to nonexistent directory."""
        original_dir = os.getcwd()
        try:
            with pytest.raises(FileNotFoundError):
                with helper.change_directory("/nonexistent/path/that/doesnt/exist"):
                    pass
        finally:
            os.chdir(original_dir)

    def test_change_directory_restores_on_exception(self, temp_dir):
        """Test directory is restored even when exception is raised."""
        original_dir = os.getcwd()
        test_dir = temp_dir / "subdir"
        test_dir.mkdir()

        try:
            with pytest.raises(ValueError):
                with helper.change_directory(str(test_dir)):
                    raise ValueError("test error")
            # Should still be back in original directory
            assert os.getcwd() == original_dir
        finally:
            os.chdir(original_dir)


class TestBuildPkgVersionIndex:
    """Tests for build_pkg_version_index function."""

    def test_build_version_index_success(self, hub_directory):
        """Test building package version index successfully."""
        index = helper.build_pkg_version_index(hub_directory)

        # Check that maintainers are in the index
        assert ("dbt-utils", "dbt-labs") in index
        assert ("dbt-expectations", "dbt-labs") in index
        assert ("dbt-profiler", "data-mie") in index

    def test_build_version_index_nonexistent_path(self, temp_dir):
        """Test error when hub path doesn't exist."""
        nonexistent = temp_dir / "nonexistent"
        with pytest.raises(helper.FileOperationError) as exc_info:
            helper.build_pkg_version_index(nonexistent)
        assert "does not exist" in str(exc_info.value)

    def test_build_version_index_file_not_dir(self, temp_dir):
        """Test error when hub path is not a directory."""
        file_path = temp_dir / "file.txt"
        file_path.write_text("content")
        with pytest.raises(helper.FileOperationError) as exc_info:
            helper.build_pkg_version_index(file_path)
        assert "not a directory" in str(exc_info.value)

    def test_build_version_index_missing_packages_dir(self, temp_dir):
        """Test error when packages directory is missing."""
        with pytest.raises(helper.FileOperationError) as exc_info:
            helper.build_pkg_version_index(temp_dir)
        assert "Packages directory not found" in str(exc_info.value)

    def test_build_version_index_with_versions(self, temp_dir):
        """Test building index with actual version files."""
        # Create hub structure
        hub_dir = temp_dir / "hub"
        packages_dir = (
            hub_dir / "data" / "packages" / "test-org" / "test-pkg" / "versions"
        )
        packages_dir.mkdir(parents=True)

        # Create version files
        (packages_dir / "1.0.0.json").write_text("{}")
        (packages_dir / "1.0.1.json").write_text("{}")

        index = helper.build_pkg_version_index(hub_dir)

        # Check that versions are indexed
        assert ("test-pkg", "test-org") in index
        assert "1.0.0" in index[("test-pkg", "test-org")]
        assert "1.0.1" in index[("test-pkg", "test-org")]

    def test_build_version_index_empty_packages_dir(self, temp_dir):
        """Test building index with empty packages directory."""
        hub_dir = temp_dir / "hub"
        (hub_dir / "data" / "packages").mkdir(parents=True)

        index = helper.build_pkg_version_index(hub_dir)
        assert index == {}


class TestGetMaintainers:
    """Tests for _get_maintainers function."""

    def test_get_maintainers(self, temp_dir):
        """Test getting list of maintainers."""
        packages_dir = temp_dir / "data" / "packages"
        packages_dir.mkdir(parents=True)

        # Create maintainer directories
        (packages_dir / "org1").mkdir()
        (packages_dir / "org2").mkdir()

        os.chdir(temp_dir)
        try:
            maintainers = helper._get_maintainers()
            assert set(maintainers) == {"org1", "org2"}
        finally:
            pass

    def test_get_maintainers_empty_dir(self, temp_dir):
        """Test getting maintainers from empty directory."""
        packages_dir = temp_dir / "data" / "packages"
        packages_dir.mkdir(parents=True)

        os.chdir(temp_dir)
        try:
            maintainers = helper._get_maintainers()
            assert maintainers == []
        finally:
            pass


class TestGetPackagesForMaintainer:
    """Tests for _get_packages_for_maintainer function."""

    def test_get_packages(self, temp_dir):
        """Test getting packages for a maintainer."""
        packages_dir = temp_dir / "data" / "packages" / "test-org"
        packages_dir.mkdir(parents=True)

        # Create package directories
        (packages_dir / "pkg1").mkdir()
        (packages_dir / "pkg2").mkdir()

        os.chdir(temp_dir)
        try:
            packages = helper._get_packages_for_maintainer("test-org")
            assert set(packages) == {"pkg1", "pkg2"}
        finally:
            pass

    def test_get_packages_nonexistent_maintainer(self, temp_dir):
        """Test getting packages for nonexistent maintainer."""
        packages_dir = temp_dir / "data" / "packages"
        packages_dir.mkdir(parents=True)

        os.chdir(temp_dir)
        try:
            packages = helper._get_packages_for_maintainer("nonexistent")
            assert packages == []
        finally:
            pass


class TestGetVersionsForPackage:
    """Tests for _get_versions_for_package function."""

    def test_get_versions(self, temp_dir):
        """Test getting versions for a package."""
        versions_dir = (
            temp_dir / "data" / "packages" / "test-org" / "test-pkg" / "versions"
        )
        versions_dir.mkdir(parents=True)

        # Create version files
        (versions_dir / "1.0.0.json").write_text("{}")
        (versions_dir / "1.0.1.json").write_text("{}")
        (versions_dir / "1.1.0.json").write_text("{}")

        os.chdir(temp_dir)
        try:
            versions = helper._get_versions_for_package("test-org", "test-pkg")
            assert set(versions) == {"1.0.0", "1.0.1", "1.1.0"}
        finally:
            pass

    def test_get_versions_no_versions_dir(self, temp_dir):
        """Test getting versions when versions directory doesn't exist."""
        packages_dir = temp_dir / "data" / "packages" / "test-org" / "test-pkg"
        packages_dir.mkdir(parents=True)

        os.chdir(temp_dir)
        try:
            versions = helper._get_versions_for_package("test-org", "test-pkg")
            assert versions == []
        finally:
            pass

    def test_get_versions_nonexistent_package(self, temp_dir):
        """Test getting versions for nonexistent package."""
        packages_dir = temp_dir / "data" / "packages"
        packages_dir.mkdir(parents=True)

        os.chdir(temp_dir)
        try:
            versions = helper._get_versions_for_package("test-org", "nonexistent")
            assert versions == []
        finally:
            pass

    def test_get_versions_ignores_non_json_files(self, temp_dir):
        """Test that non-json files are ignored."""
        versions_dir = (
            temp_dir / "data" / "packages" / "test-org" / "test-pkg" / "versions"
        )
        versions_dir.mkdir(parents=True)

        # Create version files
        (versions_dir / "1.0.0.json").write_text("{}")
        (versions_dir / "readme.txt").write_text("not a version")

        os.chdir(temp_dir)
        try:
            versions = helper._get_versions_for_package("test-org", "test-pkg")
            assert versions == ["1.0.0"]
        finally:
            pass
