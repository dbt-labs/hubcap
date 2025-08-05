"""Tests for UpdateTask fusion compatibility JSON generation"""

import json
import os
import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the classes we need to test
from hubcap.records import UpdateTask


class TestUpdateTaskFusionCompatibility(unittest.TestCase):
    """Test UpdateTask's generation of index.json and version.json with fusion compatibility"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.hub_dir = Path(self.temp_dir) / "hub.getdbt.com"
        self.package_dir = Path(self.temp_dir) / "test_org_test_package"

        # Create hub directory structure
        self.hub_dir.mkdir(parents=True)
        self.package_dir.mkdir(parents=True)

        # Create a basic dbt project in the package directory
        self._create_test_package()

        # Create UpdateTask with test data
        self.update_task = UpdateTask(
            github_username="test_org",
            github_repo_name="test_package",
            local_path_to_repo=self.package_dir,
            package_name="test_package",
            existing_tags=[],
            new_tags=["1.0.0", "1.1.0"],
            hub_repo="hub.getdbt.com",
        )

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_package(self):
        """Create a test dbt package structure"""
        # Create dbt_project.yml
        dbt_project_content = """
name: 'test_package'
version: '1.0.0'

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

target-path: "target"
clean-targets:
  - "target"
  - "dbt_packages"

models:
  test_package:
    +schema: public
    +materialized: table
"""
        with open(self.package_dir / "dbt_project.yml", "w") as f:
            f.write(dbt_project_content)

        # Create models directory and a simple model
        models_dir = self.package_dir / "models"
        models_dir.mkdir(exist_ok=True)

        model_content = """
{{ config(materialized='table') }}

select
    1 as id,
    'test' as name,
    current_timestamp as created_at
"""
        with open(models_dir / "test_model.sql", "w") as f:
            f.write(model_content)

        # Create a packages.yml file (sometimes needed)
        packages_content = """
packages:
  - package: dbt-labs/dbt_utils
    version: ">=1.0.0"
"""
        with open(self.package_dir / "packages.yml", "w") as f:
            f.write(packages_content)

    @patch("hubcap.records.git_helper.run_cmd")
    @patch("hubcap.records.subprocess.run")
    @patch("hubcap.records.package.parse_pkgs")
    @patch("hubcap.records.package.parse_require_dbt_version")
    @patch("hubcap.records.check_fusion_schema_compatibility")
    @patch("hubcap.records.UpdateTask.get_sha1")
    def test_fusion_compatible_package_json_generation(
        self,
        mock_sha1,
        mock_fusion_check,
        mock_parse_dbt_version,
        mock_parse_pkgs,
        mock_subprocess,
        mock_git_cmd,
    ):
        """Test that fusion-compatible packages generate correct JSON files"""
        # Mock returns
        mock_sha1.return_value = "abc123def456"
        mock_fusion_check.return_value = True  # Fusion compatible
        mock_parse_dbt_version.return_value = ">=1.0.0"
        mock_parse_pkgs.return_value = [
            {"name": "dbt-labs/dbt_utils", "version": ">=1.0.0"}
        ]
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Mock PR strategy
        mock_pr_strategy = MagicMock()
        mock_pr_strategy.branch_name.return_value = "test-branch"

        # Run the UpdateTask
        os.chdir(self.temp_dir)
        branch_name, org_name, package_name = self.update_task.run(
            str(self.hub_dir.parent), mock_pr_strategy
        )

        # Verify the branch and basic info
        self.assertEqual(branch_name, "test-branch")
        self.assertEqual(org_name, "test_org")
        self.assertEqual(package_name, "test_package")

        # Check that fusion compatibility was checked for each tag
        self.assertEqual(mock_fusion_check.call_count, 2)  # Called for both tags

        # Verify version-specific JSON files were created with correct fusion compatibility
        version_dir = (
            self.hub_dir
            / "data"
            / "packages"
            / "test_org"
            / "test_package"
            / "versions"
        )

        # Check 1.0.0.json
        version_1_0_0_file = version_dir / "1.0.0.json"
        self.assertTrue(version_1_0_0_file.exists())

        with open(version_1_0_0_file, "r") as f:
            version_1_0_0_spec = json.load(f)

        self.assertEqual(version_1_0_0_spec["fusion-schema-compat"], True)
        self.assertEqual(version_1_0_0_spec["name"], "test_package")
        self.assertEqual(version_1_0_0_spec["version"], "1.0.0")
        self.assertIn("downloads", version_1_0_0_spec)
        self.assertEqual(version_1_0_0_spec["downloads"]["sha1"], "abc123def456")

        # Check 1.1.0.json
        version_1_1_0_file = version_dir / "1.1.0.json"
        self.assertTrue(version_1_1_0_file.exists())

        with open(version_1_1_0_file, "r") as f:
            version_1_1_0_spec = json.load(f)

        self.assertEqual(version_1_1_0_spec["fusion-schema-compat"], True)
        self.assertEqual(version_1_1_0_spec["name"], "test_package")
        self.assertEqual(version_1_1_0_spec["version"], "1.1.0")

        # Check index.json
        index_file = (
            self.hub_dir
            / "data"
            / "packages"
            / "test_org"
            / "test_package"
            / "index.json"
        )
        self.assertTrue(index_file.exists())

        with open(index_file, "r") as f:
            index_spec = json.load(f)

        # Index should have fusion compatibility of the latest version (1.1.0)
        self.assertEqual(index_spec["fusion-schema-compat"], True)
        self.assertEqual(index_spec["name"], "test_package")
        self.assertEqual(index_spec["namespace"], "test_org")
        self.assertEqual(index_spec["latest"], "1.1.0")

    @patch("hubcap.records.git_helper.run_cmd")
    @patch("hubcap.records.subprocess.run")
    @patch("hubcap.records.package.parse_pkgs")
    @patch("hubcap.records.package.parse_require_dbt_version")
    @patch("hubcap.records.check_fusion_schema_compatibility")
    @patch("hubcap.records.UpdateTask.get_sha1")
    def test_fusion_incompatible_package_json_generation(
        self,
        mock_sha1,
        mock_fusion_check,
        mock_parse_dbt_version,
        mock_parse_pkgs,
        mock_subprocess,
        mock_git_cmd,
    ):
        """Test that fusion-incompatible packages generate correct JSON files"""
        # Mock returns
        mock_sha1.return_value = "xyz789uvw012"
        mock_fusion_check.return_value = False  # Fusion incompatible
        mock_parse_dbt_version.return_value = ">=1.0.0"
        mock_parse_pkgs.return_value = [
            {"name": "dbt-labs/dbt_utils", "version": ">=1.0.0"}
        ]
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Mock PR strategy
        mock_pr_strategy = MagicMock()
        mock_pr_strategy.branch_name.return_value = "test-branch-incompatible"

        # Run the UpdateTask
        os.chdir(self.temp_dir)
        branch_name, org_name, package_name = self.update_task.run(
            str(self.hub_dir.parent), mock_pr_strategy
        )

        # Verify basic info
        self.assertEqual(branch_name, "test-branch-incompatible")
        self.assertEqual(org_name, "test_org")
        self.assertEqual(package_name, "test_package")

        # Check that fusion compatibility was checked for each tag
        self.assertEqual(mock_fusion_check.call_count, 2)  # Called for both tags

        # Verify version-specific JSON files were created with correct fusion compatibility
        version_dir = (
            self.hub_dir
            / "data"
            / "packages"
            / "test_org"
            / "test_package"
            / "versions"
        )

        # Check 1.0.0.json
        version_1_0_0_file = version_dir / "1.0.0.json"
        self.assertTrue(version_1_0_0_file.exists())

        with open(version_1_0_0_file, "r") as f:
            version_1_0_0_spec = json.load(f)

        self.assertEqual(version_1_0_0_spec["fusion-schema-compat"], False)
        self.assertEqual(version_1_0_0_spec["name"], "test_package")
        self.assertEqual(version_1_0_0_spec["version"], "1.0.0")

        # Check 1.1.0.json
        version_1_1_0_file = version_dir / "1.1.0.json"
        self.assertTrue(version_1_1_0_file.exists())

        with open(version_1_1_0_file, "r") as f:
            version_1_1_0_spec = json.load(f)

        self.assertEqual(version_1_1_0_spec["fusion-schema-compat"], False)
        self.assertEqual(version_1_1_0_spec["name"], "test_package")
        self.assertEqual(version_1_1_0_spec["version"], "1.1.0")

        # Check index.json
        index_file = (
            self.hub_dir
            / "data"
            / "packages"
            / "test_org"
            / "test_package"
            / "index.json"
        )
        self.assertTrue(index_file.exists())

        with open(index_file, "r") as f:
            index_spec = json.load(f)

        # Index should have fusion compatibility of the latest version (1.1.0)
        self.assertEqual(index_spec["fusion-schema-compat"], False)
        self.assertEqual(index_spec["name"], "test_package")
        self.assertEqual(index_spec["namespace"], "test_org")
        self.assertEqual(index_spec["latest"], "1.1.0")

    @patch("hubcap.records.git_helper.run_cmd")
    @patch("hubcap.records.subprocess.run")
    @patch("hubcap.records.package.parse_pkgs")
    @patch("hubcap.records.package.parse_require_dbt_version")
    @patch("hubcap.records.check_fusion_schema_compatibility")
    @patch("hubcap.records.UpdateTask.get_sha1")
    def test_mixed_fusion_compatibility_versions(
        self,
        mock_sha1,
        mock_fusion_check,
        mock_parse_dbt_version,
        mock_parse_pkgs,
        mock_subprocess,
        mock_git_cmd,
    ):
        """Test packages with mixed fusion compatibility across versions"""
        # Mock returns - different compatibility for different versions
        mock_sha1.return_value = "mixed123compat"
        mock_parse_dbt_version.return_value = ">=1.0.0"
        mock_parse_pkgs.return_value = []
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Mock fusion compatibility check to return different values for different calls
        # First call (1.0.0): incompatible, Second call (1.1.0): compatible
        mock_fusion_check.side_effect = [False, True]

        # Mock PR strategy
        mock_pr_strategy = MagicMock()
        mock_pr_strategy.branch_name.return_value = "test-branch-mixed"

        # Run the UpdateTask
        os.chdir(self.temp_dir)
        branch_name, org_name, package_name = self.update_task.run(
            str(self.hub_dir.parent), mock_pr_strategy
        )

        # Verify basic info
        self.assertEqual(branch_name, "test-branch-mixed")

        # Check that fusion compatibility was checked for each tag
        self.assertEqual(mock_fusion_check.call_count, 2)

        # Verify version-specific JSON files have correct individual compatibility
        version_dir = (
            self.hub_dir
            / "data"
            / "packages"
            / "test_org"
            / "test_package"
            / "versions"
        )

        # Check 1.0.0.json (should be incompatible)
        with open(version_dir / "1.0.0.json", "r") as f:
            version_1_0_0_spec = json.load(f)
        self.assertEqual(version_1_0_0_spec["fusion-schema-compat"], False)

        # Check 1.1.0.json (should be compatible)
        with open(version_dir / "1.1.0.json", "r") as f:
            version_1_1_0_spec = json.load(f)
        self.assertEqual(version_1_1_0_spec["fusion-schema-compat"], True)

        # Check index.json (should reflect latest version - 1.1.0 - which is compatible)
        index_file = (
            self.hub_dir
            / "data"
            / "packages"
            / "test_org"
            / "test_package"
            / "index.json"
        )
        with open(index_file, "r") as f:
            index_spec = json.load(f)

        self.assertEqual(
            index_spec["fusion-schema-compat"], True
        )  # Latest version (1.1.0) is compatible
        self.assertEqual(index_spec["latest"], "1.1.0")

    @patch("hubcap.records.git_helper.run_cmd")
    @patch("hubcap.records.subprocess.run")
    @patch("hubcap.records.package.parse_pkgs")
    @patch("hubcap.records.package.parse_require_dbt_version")
    @patch("hubcap.records.check_fusion_schema_compatibility")
    @patch("hubcap.records.UpdateTask.get_sha1")
    def test_existing_index_file_fusion_compatibility_update(
        self,
        mock_sha1,
        mock_fusion_check,
        mock_parse_dbt_version,
        mock_parse_pkgs,
        mock_subprocess,
        mock_git_cmd,
    ):
        """Test that existing index.json files are properly updated with new fusion compatibility"""
        # Create existing index.json with old data
        index_dir = self.hub_dir / "data" / "packages" / "test_org" / "test_package"
        index_dir.mkdir(parents=True, exist_ok=True)

        existing_index = {
            "name": "test_package",
            "namespace": "test_org",
            "description": "A test package for fusion compatibility",
            "latest": "0.9.0",
            "fusion-schema-compat": False,  # Old version was incompatible
            "assets": {"logo": "logos/custom.svg"},
        }

        with open(index_dir / "index.json", "w") as f:
            json.dump(existing_index, f)

        # Mock returns for new version
        mock_sha1.return_value = "update123test"
        mock_fusion_check.return_value = True  # New version is compatible
        mock_parse_dbt_version.return_value = ">=1.0.0"
        mock_parse_pkgs.return_value = []
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Mock PR strategy
        mock_pr_strategy = MagicMock()
        mock_pr_strategy.branch_name.return_value = "test-branch-update"

        # Update existing tags to include the old version
        self.update_task.existing_tags = ["0.9.0"]

        # Run the UpdateTask
        os.chdir(self.temp_dir)
        self.update_task.run(str(self.hub_dir.parent), mock_pr_strategy)

        # Check updated index.json
        with open(index_dir / "index.json", "r") as f:
            updated_index = json.load(f)

        # Should preserve existing description and assets
        self.assertEqual(
            updated_index["description"], "A test package for fusion compatibility"
        )
        self.assertEqual(updated_index["assets"]["logo"], "logos/custom.svg")

        # Should update latest version and fusion compatibility
        self.assertEqual(updated_index["latest"], "1.1.0")  # Latest new tag
        self.assertEqual(
            updated_index["fusion-schema-compat"], True
        )  # New latest version is compatible
        self.assertEqual(updated_index["name"], "test_package")
        self.assertEqual(updated_index["namespace"], "test_org")

    def test_fusion_compatibility_directory_bug(self):
        """Test that fusion compatibility is checked on the correct directory"""
        # This test is designed to catch the bug where fusion compatibility
        # is checked on the wrong directory (hub dir instead of package dir)

        with patch(
            "hubcap.records.check_fusion_schema_compatibility"
        ) as mock_fusion_check:
            with patch("hubcap.records.git_helper.run_cmd"):
                with patch("hubcap.records.subprocess.run") as mock_subprocess:
                    with patch("hubcap.records.package.parse_pkgs") as mock_parse_pkgs:
                        with patch(
                            "hubcap.records.package.parse_require_dbt_version"
                        ) as mock_parse_dbt_version:
                            with patch(
                                "hubcap.records.UpdateTask.get_sha1"
                            ) as mock_sha1:
                                # Setup mocks
                                mock_fusion_check.return_value = True
                                mock_subprocess.return_value = MagicMock(returncode=0)
                                mock_parse_pkgs.return_value = []
                                mock_parse_dbt_version.return_value = ">=1.0.0"
                                mock_sha1.return_value = "test123"

                                # Mock PR strategy
                                mock_pr_strategy = MagicMock()
                                mock_pr_strategy.branch_name.return_value = (
                                    "test-branch"
                                )

                                # Set up a single tag for simpler testing
                                self.update_task.new_tags = ["1.0.0"]

                                # Run the UpdateTask
                                os.chdir(self.temp_dir)
                                self.update_task.run(
                                    str(self.hub_dir.parent), mock_pr_strategy
                                )

                                # Verify that fusion compatibility was called with the package directory
                                # NOT the hub directory
                                mock_fusion_check.assert_called_once()

                                # Get the actual call argument
                                actual_call_path = mock_fusion_check.call_args[0][0]

                                # Verify that fusion compatibility was called with the package directory
                                print(
                                    f"Fusion compatibility called with path: {actual_call_path}"
                                )
                                print(
                                    f"Expected package path: {self.update_task.local_path_to_repo}"
                                )
                                print(f"Current working directory: {os.getcwd()}")

                                # This should now pass after fixing the bug
                                self.assertEqual(
                                    str(actual_call_path),
                                    str(self.update_task.local_path_to_repo),
                                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
