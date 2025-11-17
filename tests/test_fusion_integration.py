"""Integration tests for the check_fusion_schema_compatibility function"""

import os
import tempfile
import unittest
import shutil
from pathlib import Path

# Import the actual function from the hubcap.records module
from hubcap.records import check_fusion_schema_compatibility


class TestFusionSchemaCompatibilityIntegration(unittest.TestCase):
    """Integration test cases that actually run dbtf parse"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a temporary directory for each test
        self.temp_dir = tempfile.mkdtemp()
        self.repo_path = Path(self.temp_dir)

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
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_basic_dbt_project(self, project_name="test_package"):
        """Create a basic dbt project structure"""
        # Create dbt_project.yml
        dbt_project_content = f"""
name: '{project_name}'
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
  {project_name}:
    +schema: public
    +materialized: table

vars:
  # Variables for testing
  test_var: "test_value"
"""
        with open(self.repo_path / "dbt_project.yml", "w") as f:
            f.write(dbt_project_content)

        # Create directories
        for dir_name in ["models", "tests", "macros", "seeds", "snapshots", "analyses"]:
            (self.repo_path / dir_name).mkdir(exist_ok=True)

    def _create_simple_model(self, model_name="test_model"):
        """Create a simple dbt model"""
        models_dir = self.repo_path / "models"
        models_dir.mkdir(exist_ok=True)

        model_content = """
{{ config(materialized='table') }}

select
    1 as id,
    'test' as name,
    current_timestamp as created_at
"""
        with open(models_dir / f"{model_name}.sql", "w") as f:
            f.write(model_content)

    def _create_fusion_compatible_model(self):
        """Create a model that should be fusion schema compatible"""
        models_dir = self.repo_path / "models"
        models_dir.mkdir(exist_ok=True)

        # Simple select statement that should be fusion compatible
        model_content = """
{{ config(materialized='table') }}

select
    cast(1 as integer) as id,
    cast('test' as varchar(50)) as name,
    cast(current_timestamp as timestamp) as created_at
"""
        with open(models_dir / "fusion_compatible_model.sql", "w") as f:
            f.write(model_content)

    def _create_potentially_incompatible_model(self):
        """Create a model that might have fusion compatibility issues"""
        models_dir = self.repo_path / "models"
        models_dir.mkdir(exist_ok=True)

        # Model with complex transformations that might cause fusion issues
        model_content = """
{{ config(materialized='table') }}

select
    id,
    name,
    case
        when length(name) > 10 then 'long'
        else 'short'
    end as name_category,
    row_number() over (partition by name order by id) as row_num
from (
    select 1 as id, 'test' as name
    union all
    select 2 as id, 'another_test_name' as name
) base_data
"""
        with open(models_dir / "complex_model.sql", "w") as f:
            f.write(model_content)

    def test_dbtf_command_available(self):
        """Test if dbtf command or dbt-fusion is available in the environment"""
        import subprocess

        try:
            # Try dbtf first
            result = subprocess.run(
                ["dbtf", "--version"], capture_output=True, timeout=10
            )
            if result.returncode == 0:
                print(f"dbtf version: {result.stdout.decode().strip()}")
                return True
        except FileNotFoundError:
            pass

        try:
            # Fall back to dbt command, but it must be dbt-fusion
            result = subprocess.run(
                ["dbt", "--version"], capture_output=True, timeout=10
            )
            if result.returncode == 0:
                output = result.stdout.decode().strip()
                print(f"dbt version: {output}")
                if "dbt-fusion" in output:
                    return True
                else:
                    self.fail(
                        "dbt-fusion is required for fusion compatibility integration tests, but found regular dbt-core instead"
                    )
            else:
                self.fail("dbt command returned non-zero exit code")
        except FileNotFoundError:
            self.fail(
                "Neither dbtf nor dbt command found in PATH - dbt-fusion is required for integration tests"
            )
        except subprocess.TimeoutExpired:
            self.fail("dbt command timed out")

    def test_fusion_compatibility_simple_project(self):
        """Test fusion compatibility with a simple dbt project"""
        # Check if dbtf is available
        self.test_dbtf_command_available()

        # Create a basic project
        self._create_basic_dbt_project("simple_test")
        self._create_fusion_compatible_model()

        # Test fusion compatibility
        result = check_fusion_schema_compatibility(self.repo_path)

        # Since we have dbt-fusion available and this is a simple valid project, it should be compatible
        self.assertTrue(result, "Simple dbt project should be fusion schema compatible")
        print(f"Simple project fusion compatibility: {result}")

    def test_fusion_compatibility_complex_project(self):
        """Test fusion compatibility with a more complex dbt project"""
        # Check if dbtf is available
        self.test_dbtf_command_available()

        # Create a project with potentially complex models
        self._create_basic_dbt_project("complex_test")
        self._create_fusion_compatible_model()
        self._create_potentially_incompatible_model()

        # Test fusion compatibility
        result = check_fusion_schema_compatibility(self.repo_path)

        # Since we have dbt-fusion available and this is a valid project, it should be compatible
        self.assertTrue(
            result, "Complex dbt project should be fusion schema compatible"
        )
        print(f"Complex project fusion compatibility: {result}")

    def test_fusion_compatibility_empty_project(self):
        """Test fusion compatibility with an empty dbt project"""
        # Check if dbtf is available
        self.test_dbtf_command_available()

        # Create a basic project with no models
        self._create_basic_dbt_project("empty_test")

        # Test fusion compatibility - empty project should be compatible
        result = check_fusion_schema_compatibility(self.repo_path)

        self.assertTrue(result, "Empty dbt project should be fusion schema compatible")
        print(f"Empty project fusion compatibility: {result}")

    def test_profiles_yml_creation_and_cleanup(self):
        """Test that profiles.yml is created and cleaned up properly"""
        # Check if dbtf is available
        self.test_dbtf_command_available()

        self._create_basic_dbt_project("cleanup_test")
        self._create_simple_model()

        profiles_path = self.repo_path / "profiles.yml"

        # Ensure profiles.yml doesn't exist before
        self.assertFalse(profiles_path.exists())

        # Run the function
        result = check_fusion_schema_compatibility(self.repo_path)

        # Ensure profiles.yml is cleaned up after
        self.assertFalse(profiles_path.exists())
        # Since this is a valid project with dbt-fusion available, it should be compatible
        self.assertTrue(result, "Valid dbt project should be fusion schema compatible")

    def test_environment_variable_setting(self):
        """Test that _DBT_FUSION_STRICT_MODE is set during execution"""
        # Check if dbtf is available
        self.test_dbtf_command_available()

        self._create_basic_dbt_project("env_test")
        self._create_simple_model()

        # Clear environment variable if set
        if "_DBT_FUSION_STRICT_MODE" in os.environ:
            del os.environ["_DBT_FUSION_STRICT_MODE"]

        # Run the function
        result = check_fusion_schema_compatibility(self.repo_path)

        # Since this is a valid project with dbt-fusion available, it should be compatible
        self.assertTrue(result, "Valid dbt project should be fusion schema compatible")
        # The function should have set the environment variable during execution
        self.assertEqual(os.environ.get("_DBT_FUSION_STRICT_MODE"), "1")

    def test_invalid_dbt_project(self):
        """Test behavior with an invalid dbt project"""
        # Check if dbtf is available
        self.test_dbtf_command_available()

        # Create an invalid dbt_project.yml
        invalid_content = "invalid: yaml: content:"
        with open(self.repo_path / "dbt_project.yml", "w") as f:
            f.write(invalid_content)

        # This should return False due to the invalid project
        result = check_fusion_schema_compatibility(self.repo_path)

        # Should return False for invalid projects
        self.assertFalse(result)

    def test_missing_dbt_project_yml(self):
        """Test behavior when dbt_project.yml is missing"""
        # Check if dbtf is available
        self.test_dbtf_command_available()

        # Don't create dbt_project.yml - just use empty directory

        # This should return False due to missing dbt_project.yml
        result = check_fusion_schema_compatibility(self.repo_path)

        # Should return False for missing project file
        self.assertFalse(result)


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
