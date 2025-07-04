#!/usr/bin/env python3
"""
hubcap Dry Run Script

This script runs hubcap in dry-run mode, performing all operations including
cloning repositories and processing packages, but without pushing any changes
to git. It's designed to run in CI/CD to catch configuration and package errors early.
"""

import os
import sys
import logging
import tempfile
from pathlib import Path

# Import hubcap modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hubcap import helper, package_maintainers, package  # noqa E402


def main():
    """Dry run version of hubcap that performs all operations except git pushes"""
    try:
        logging.info("Starting hubcap dry run validation...")

        # Test configuration loading
        logging.info("Testing configuration loading...")

        config = helper.build_config()  # noqa: F841
        logging.info("✅ Configuration loaded successfully")

        # Test package maintainers loading
        logging.info("Testing package maintainers loading...")
        maintainers = package_maintainers.load_package_maintainers()
        logging.info(f"✅ Loaded {len(maintainers)} package maintainers")

        # Create temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            logging.info(f"Using temporary directory: {temp_path}")

            # Clone package repositories
            logging.info("Cloning package repositories...")
            failed_repos = package.clone_package_repos(maintainers, temp_path)

            if failed_repos:
                logging.error(
                    f"❌ Failed to clone {len(failed_repos)} repositories: {', '.join(failed_repos)}"
                )
                raise Exception(
                    f"Repository cloning failed for: {', '.join(failed_repos)}"
                )

            logging.info("✅ All repositories cloned successfully")

            # Test package parsing and validation
            logging.info("Testing package parsing and validation...")
            total_packages = 0
            failed_packages = []

            for maintainer in maintainers:
                logging.info(f"  Processing maintainer: {maintainer.get_name()}")
                packages = maintainer.get_packages()
                total_packages += len(packages)

                for package_name in packages:
                    repo_path = temp_path / f"{maintainer.get_name()}_{package_name}"

                    if not repo_path.exists():
                        failed_packages.append(
                            f"{package_name} (repository not cloned)"
                        )
                        logging.error(f"    ❌ {package_name}: Repository not cloned")
                        continue

                    try:
                        # Test dbt_project.yml parsing
                        package_name_from_yml = package.parse_pkg_name(repo_path)
                        logging.info(f"    ✅ {package_name} -> {package_name_from_yml}")
                    except Exception as e:
                        failed_packages.append(f"{package_name} ({str(e)})")
                        logging.error(f"    ❌ {package_name}: {str(e)}")

            if failed_packages:
                raise Exception(
                    f"Package validation failed for {len(failed_packages)} packages: {', '.join(failed_packages)}"
                )

            logging.info(f"✅ All {total_packages} packages processed successfully")

        logging.info("✅ hubcap dry run completed successfully - all validations passed")
        return 0

    except Exception as e:
        logging.error(f"❌ hubcap dry run failed: {str(e)}")
        return 1


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sys.exit(main())
