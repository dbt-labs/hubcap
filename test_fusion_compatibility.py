"""Unit tests for the check_fusion_schema_compatibility function"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

# Import the actual function from the hubcap.records module
from hubcap.records import check_fusion_schema_compatibility


class TestCheckFusionSchemaCompatibility(unittest.TestCase):
    """Test cases for check_fusion_schema_compatibility function"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary directory for each test
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)

        # Create a minimal dbt_project.yml file
        dbt_project_content = """
name: 'test_package'
version: '1.0.0'
profile: 'test_schema_compat'

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
"""
        with open(self.repo_path / "dbt_project.yml", "w") as f:
            f.write(dbt_project_content)

        # Store original environment state
        self.original_env = os.environ.get("_DBT_FUSION_STRICT_MODE")

    def tearDown(self):
        """Clean up test fixtures"""
        # Restore original environment
        if self.original_env is not None:
            os.environ["_DBT_FUSION_STRICT_MODE"] = self.original_env
        elif "_DBT_FUSION_STRICT_MODE" in os.environ:
            del os.environ["_DBT_FUSION_STRICT_MODE"]

        # Clean up temp directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("hubcap.records.subprocess.run")
    def test_fusion_compatible_success(self, mock_subprocess):
        """Test successful fusion compatibility check"""
        # Mock successful dbtf parse command
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # Run the function
        result = check_fusion_schema_compatibility(self.repo_path)

        # Assertions
        self.assertTrue(result)

        # Verify subprocess was called with correct arguments
        mock_subprocess.assert_called_once_with(
            [
                "dbtf",
                "parse",
                "--profile",
                "test_schema_compat",
                "--project-dir",
                str(self.repo_path),
            ],
            capture_output=True,
            timeout=60,
        )

        # Verify environment variable was set
        self.assertEqual(os.environ.get("_DBT_FUSION_STRICT_MODE"), "1")

        # Verify profiles.yml was cleaned up
        profiles_path = self.repo_path / "profiles.yml"
        self.assertFalse(profiles_path.exists())

    @patch("hubcap.records.subprocess.run")
    def test_fusion_incompatible_failure(self, mock_subprocess):
        """Test failed fusion compatibility check"""
        # Mock failed dbtf parse command
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        # Run the function
        result = check_fusion_schema_compatibility(self.repo_path)

        # Assertions
        self.assertFalse(result)

        # Verify subprocess was called
        mock_subprocess.assert_called_once()

        # Verify profiles.yml was cleaned up
        profiles_path = self.repo_path / "profiles.yml"
        self.assertFalse(profiles_path.exists())

    @patch("hubcap.records.subprocess.run")
    def test_profiles_yml_creation_and_content(self, mock_subprocess):
        """Test that profiles.yml is created with correct content"""
        # Mock successful command
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # Capture the profiles.yml content during execution
        profiles_content = None

        def capture_profiles_content(*args, **kwargs):
            nonlocal profiles_content
            profiles_path = self.repo_path / "profiles.yml"
            if profiles_path.exists():
                with open(profiles_path, "r") as f:
                    profiles_content = f.read()
            return mock_result

        mock_subprocess.side_effect = capture_profiles_content

        # Run the function
        check_fusion_schema_compatibility(self.repo_path)

        # Verify profiles.yml content
        self.assertIsNotNone(profiles_content)
        self.assertIn("test_schema_compat:", profiles_content)
        self.assertIn("type: postgres", profiles_content)
        self.assertIn("host: localhost", profiles_content)
        self.assertIn("port: 5432", profiles_content)
        self.assertIn("user: postgres", profiles_content)
        self.assertIn("password: postgres", profiles_content)
        self.assertIn("dbname: postgres", profiles_content)
        self.assertIn("schema: public", profiles_content)

    @patch("hubcap.records.subprocess.run")
    def test_timeout_handling(self, mock_subprocess):
        """Test timeout scenario"""
        # Mock timeout exception
        mock_subprocess.side_effect = subprocess.TimeoutExpired(
            cmd=["dbtf", "parse"], timeout=60
        )

        # Run the function
        result = check_fusion_schema_compatibility(self.repo_path)

        # Assertions
        self.assertFalse(result)

        # Verify profiles.yml was cleaned up even after timeout
        profiles_path = self.repo_path / "profiles.yml"
        self.assertFalse(profiles_path.exists())

    @patch("hubcap.records.subprocess.run")
    def test_file_not_found_handling(self, mock_subprocess):
        """Test FileNotFoundError scenario (dbtf command not available)"""
        # Mock FileNotFoundError
        mock_subprocess.side_effect = FileNotFoundError("dbtf command not found")

        # Run the function
        result = check_fusion_schema_compatibility(self.repo_path)

        # Assertions
        self.assertFalse(result)

        # Verify profiles.yml was cleaned up
        profiles_path = self.repo_path / "profiles.yml"
        self.assertFalse(profiles_path.exists())

    @patch("hubcap.records.subprocess.run")
    def test_general_exception_handling(self, mock_subprocess):
        """Test general exception handling"""
        # Mock a general exception
        mock_subprocess.side_effect = Exception("Unexpected error")

        # Run the function
        result = check_fusion_schema_compatibility(self.repo_path)

        # Assertions
        self.assertFalse(result)

        # Verify profiles.yml was cleaned up
        profiles_path = self.repo_path / "profiles.yml"
        self.assertFalse(profiles_path.exists())

    @patch("hubcap.records.subprocess.run")
    def test_existing_profiles_yml_handling(self, mock_subprocess):
        """Test behavior when profiles.yml already exists"""
        # Create an existing profiles.yml file
        existing_content = "existing_profile:\n  target: dev\n"
        profiles_path = self.repo_path / "profiles.yml"
        with open(profiles_path, "w") as f:
            f.write(existing_content)

        # Mock successful command
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # Run the function
        result = check_fusion_schema_compatibility(self.repo_path)

        # Assertions
        self.assertTrue(result)

        # Verify the original file is gone (it gets removed)
        self.assertFalse(profiles_path.exists())

    @patch("hubcap.records.logging.info")
    @patch("hubcap.records.subprocess.run")
    def test_logging_success(self, mock_subprocess, mock_logging):
        """Test that success is logged correctly"""
        # Mock successful command
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        # Run the function
        check_fusion_schema_compatibility(self.repo_path)

        # Verify logging was called with success message
        mock_logging.assert_called_with(
            f"Package at {self.repo_path} is fusion schema compatible"
        )

    @patch("hubcap.records.logging.info")
    @patch("hubcap.records.subprocess.run")
    def test_logging_failure(self, mock_subprocess, mock_logging):
        """Test that failure is logged correctly"""
        # Mock failed command
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_subprocess.return_value = mock_result

        # Run the function
        check_fusion_schema_compatibility(self.repo_path)

        # Verify logging was called with failure message
        mock_logging.assert_called_with(
            f"Package at {self.repo_path} is not fusion schema compatible"
        )

    @patch("hubcap.records.logging.warning")
    @patch("hubcap.records.subprocess.run")
    def test_logging_timeout(self, mock_subprocess, mock_logging):
        """Test that timeout is logged correctly"""
        # Mock timeout
        mock_subprocess.side_effect = subprocess.TimeoutExpired(
            cmd=["dbtf", "parse"], timeout=60
        )

        # Run the function
        check_fusion_schema_compatibility(self.repo_path)

        # Verify logging was called with timeout message
        mock_logging.assert_called_with(
            f"dbtf parse timed out for package at {self.repo_path}"
        )

    def test_environment_variable_set(self):
        """Test that _DBT_FUSION_STRICT_MODE environment variable is properly set"""
        with patch("hubcap.records.subprocess.run") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_subprocess.return_value = mock_result

            # Ensure env var is not set initially
            if "_DBT_FUSION_STRICT_MODE" in os.environ:
                del os.environ["_DBT_FUSION_STRICT_MODE"]

            # Run the function
            check_fusion_schema_compatibility(self.repo_path)

            # Verify environment variable was set to "1"
            self.assertEqual(os.environ.get("_DBT_FUSION_STRICT_MODE"), "1")

    def test_profiles_yml_cleanup_on_file_creation_failure(self):
        """Test that cleanup works even if file creation fails"""
        # Make the directory read-only to cause file creation to fail
        self.repo_path.chmod(0o444)

        try:
            result = check_fusion_schema_compatibility(self.repo_path)
            # Should return False due to the exception
            self.assertFalse(result)
        finally:
            # Restore permissions for cleanup
            self.repo_path.chmod(0o755)


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
