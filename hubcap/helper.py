"""Environment setup and state generation for hubcap"""

import datetime
import json
import logging
import os
from contextlib import contextmanager
from typing import Dict, Any, List

from pathlib import Path


class ConfigurationError(Exception):
    """Custom exception for configuration errors"""

    pass


class FileOperationError(Exception):
    """Custom exception for file operation errors"""

    pass


NOW = int(datetime.datetime.now().timestamp())

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


@contextmanager
def change_directory(path):
    """Context manager for temporarily changing directory"""
    prev_path = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(prev_path)


def build_config() -> Dict[str, Any]:
    """Pull the config env variable which holds github secrets"""
    try:
        config_str = os.environ.get("CONFIG")
        if not config_str:
            raise ConfigurationError("CONFIG environment variable is not set")

        try:
            config = json.loads(config_str)
            if not isinstance(config, dict):
                raise ConfigurationError("CONFIG must be a valid JSON object")
            return config
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                f"Invalid JSON in CONFIG environment variable: {str(e)}"
            )
    except Exception as e:
        if isinstance(e, ConfigurationError):
            raise
        raise ConfigurationError(f"Unexpected error loading configuration: {str(e)}")


def _get_maintainers() -> List[str]:
    """Get list of maintainers from the packages directory"""
    try:
        packages_path = Path("data") / Path("packages")
        maintainers = [d.name for d in packages_path.iterdir() if d.is_dir()]
        return maintainers
    except OSError as e:
        raise FileOperationError(f"Error reading maintainers directory: {str(e)}")


def _get_packages_for_maintainer(maintainer: str) -> List[str]:
    """Get list of packages for a specific maintainer"""
    try:
        maintainer_path = Path("data") / Path("packages") / Path(maintainer)
        packages = [p.name for p in maintainer_path.iterdir() if p.is_dir()]
        return packages
    except OSError as e:
        logging.error(f"Error reading packages for maintainer {maintainer}: {str(e)}")
        return []


def _get_versions_for_package(maintainer: str, package: str) -> List[str]:
    """Get list of versions for a specific package"""
    try:
        package_path = Path("data") / "packages" / maintainer / package
        if not package_path.exists():
            logging.error(f"Package path does not exist: {package_path}")
            return []

        versions_dir = package_path / "versions"
        if not versions_dir.exists():
            return []

        try:
            version_files = list(versions_dir.glob("*.json"))
            versions = [
                f.stem  # Use stem to get filename without extension
                for f in version_files
                if f.is_file()
            ]
            return versions
        except OSError as e:
            logging.error(
                f"Error reading versions for {maintainer}/{package}: {str(e)}"
            )
            return []
    except Exception as e:
        logging.error(f"Error processing package {maintainer}/{package}: {str(e)}")
        return []


def build_pkg_version_index(hub_path) -> Dict[tuple, list]:
    """traverse the hub repo and load all versions for every package of every org into memory"""
    try:
        # Validate hub_path exists and is a directory
        hub_path = Path(hub_path)
        if not hub_path.exists():
            raise FileOperationError(f"Hub directory does not exist: {hub_path}")
        if not hub_path.is_dir():
            raise FileOperationError(f"Hub path is not a directory: {hub_path}")

        # Check if the expected structure exists
        packages_dir = hub_path / "data" / "packages"
        if not packages_dir.exists():
            raise FileOperationError(f"Packages directory not found: {packages_dir}")

        with change_directory(hub_path):
            maintainers = _get_maintainers()

            if not maintainers:
                logging.error("No maintainers found in packages directory")
                return {}

            package_version_index = {}
            for maintainer in maintainers:
                packages = _get_packages_for_maintainer(maintainer)

                for package in packages:
                    versions = _get_versions_for_package(maintainer, package)
                    package_version_index[(package, maintainer)] = versions

            return package_version_index

    except Exception as e:
        if isinstance(e, (ConfigurationError, FileOperationError)):
            raise
        raise FileOperationError(
            f"Unexpected error building package version index: {str(e)}"
        )
