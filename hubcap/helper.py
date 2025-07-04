"""Environment setup and state generation for hubcap"""

import datetime
import json
import logging
import os
from typing import Dict, Any

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

        # store previous path for easy return at function exit
        prev_path = os.getcwd()
        os.chdir(hub_path)

        try:
            # Get list of maintainers
            maintainers = []
            try:
                maintainers = [
                    d
                    for d in os.listdir(Path("data") / Path("packages"))
                    if (Path("data") / Path("packages") / d).is_dir()
                ]
            except OSError as e:
                raise FileOperationError(
                    f"Error reading maintainers directory: {str(e)}"
                )

            if not maintainers:
                logging.warning("No maintainers found in packages directory")
                return {}

            maintainer_package_map = {}
            for maintainer in maintainers:
                try:
                    maintainer_path = Path("data") / Path("packages") / Path(maintainer)
                    packages = [
                        p
                        for p in os.listdir(maintainer_path)
                        if (maintainer_path / p).is_dir()
                    ]
                    maintainer_package_map[maintainer] = packages
                except OSError as e:
                    logging.warning(
                        f"Error reading packages for maintainer {maintainer}: {str(e)}"
                    )
                    maintainer_package_map[maintainer] = []

            package_version_index = {}
            for maintainer in maintainer_package_map.keys():
                for package in maintainer_package_map[maintainer]:
                    try:
                        package_path = Path("data") / "packages" / maintainer / package
                        if not package_path.exists():
                            logging.warning(
                                f"Package path does not exist: {package_path}"
                            )
                            continue

                        # Find all version JSON files
                        versions = []
                        versions_dir = package_path / "versions"
                        if versions_dir.exists():
                            try:
                                version_files = list(versions_dir.glob("*.json"))
                                versions = [
                                    os.path.basename(f)[
                                        : -len(".json")
                                    ]  # include semver in filename only
                                    for f in version_files
                                    if f.is_file()
                                ]
                            except OSError as e:
                                logging.warning(
                                    f"Error reading versions for {maintainer}/{package}: {str(e)}"
                                )
                                versions = []

                        package_version_index[(package, maintainer)] = versions
                    except Exception as e:
                        logging.warning(
                            f"Error processing package {maintainer}/{package}: {str(e)}"
                        )
                        package_version_index[(package, maintainer)] = []

            return package_version_index

        finally:
            os.chdir(prev_path)

    except Exception as e:
        if isinstance(e, (ConfigurationError, FileOperationError)):
            raise
        raise FileOperationError(
            f"Unexpected error building package version index: {str(e)}"
        )
