"""Shared fixtures and configuration for tests."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from dbt_fusion_package_tools.compatibility import FusionConformanceResult, ParseConformanceLogOutput, FusionLogMessage


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config():
    """Provide a mock configuration dictionary."""
    return {
        "org": "dbt-labs",
        "repo": "hub.getdbt.com",
        "push_branches": True,
        "one_branch_per_repo": True,
        "user": {
            "name": "test-bot",
            "email": "test@example.com",
            "token": "test-token-123",
        },
    }


@pytest.fixture
def mock_config_env(mock_config, monkeypatch):
    """Set up a mock CONFIG environment variable."""
    monkeypatch.setenv("CONFIG", json.dumps(mock_config))
    return mock_config


@pytest.fixture
def sample_dbt_project_yml():
    """Provide sample dbt_project.yml content."""
    return {
        "name": "my_awesome_package",
        "version": "1.0.0",
        "config-version": 2,
        "require-dbt-version": [">=1.0.0", "<2.0.0"],
        "profile": "my_profile",
    }


@pytest.fixture
def sample_packages_yml():
    """Provide sample packages.yml content."""
    return {
        "packages": [
            {"git": "https://github.com/dbt-labs/dbt-utils.git", "revision": "0.7.0"},
            {"local": "relative/path/to/local_dependency"},
        ]
    }


@pytest.fixture
def sample_hub_json():
    """Provide sample hub.json content."""
    return {
        "dbt-labs": ["dbt-utils", "dbt-expectations", "dbt-codegen"],
        "data-mie": ["dbt-profiler"],
    }


@pytest.fixture
def sample_exclusions_json():
    """Provide sample exclusions.json content."""
    return {"dbt-labs": ["excluded-package"]}


@pytest.fixture
def hub_directory(
    temp_dir, sample_hub_json, sample_exclusions_json, sample_dbt_project_yml
):
    """Create a mock hub directory structure."""
    hub_dir = temp_dir / "hub.getdbt.com"
    hub_dir.mkdir()

    # Create hub.json
    (hub_dir / "hub.json").write_text(json.dumps(sample_hub_json))

    # Create exclusions.json
    (hub_dir / "exclusions.json").write_text(json.dumps(sample_exclusions_json))

    # Create data/packages structure
    packages_dir = hub_dir / "data" / "packages"
    packages_dir.mkdir(parents=True)

    # Create some sample package structure
    for org, packages in sample_hub_json.items():
        org_dir = packages_dir / org
        org_dir.mkdir(exist_ok=True)

        for pkg in packages:
            pkg_dir = org_dir / pkg
            pkg_dir.mkdir(exist_ok=True)
            versions_dir = pkg_dir / "versions"
            versions_dir.mkdir(exist_ok=True)

    return hub_dir


@pytest.fixture
def package_repo_dir(temp_dir, sample_dbt_project_yml, sample_packages_yml):
    """Create a mock package repository directory."""
    repo_dir = temp_dir / "test_package_repo"
    repo_dir.mkdir()

    # Write dbt_project.yml
    (repo_dir / "dbt_project.yml").write_text(
        "name: test_package\nversion: 1.0.0\nconfig-version: 2\n"
    )

    # Write packages.yml
    (repo_dir / "packages.yml").write_text(
        "packages:\n"
        "  - git: https://github.com/dbt-labs/dbt-utils.git\n"
        "    revision: 0.7.0\n"
    )

    return repo_dir


@pytest.fixture
def mock_repo():
    """Provide a mock GitPython Repo object."""
    repo = MagicMock()
    repo.working_dir = "/mock/repo/path"
    repo.remotes.origin.pull = MagicMock()
    repo.git.tag = MagicMock(return_value="v1.0.0\nv1.0.1\nv1.0.2")
    repo.git.fetch = MagicMock()
    repo.git.checkout = MagicMock()
    return repo


@pytest.fixture
def mock_fusion_conformance_output():
    """Provide a mock FusionConformanceResult object."""
    return FusionConformanceResult(
        version="1.0.0", 
        require_dbt_version_defined=True, 
        require_dbt_version_compatible=True,
        parse_compatibility_result=ParseConformanceLogOutput(
            parse_exit_code=1,
            total_errors=1,
            total_warnings=0,
            errors=[FusionLogMessage(
                body="Sample error message",
                error_code=1060
            )],
            warnings=[],
            fusion_version="2.0.0-preview-v101",
        )
    )
