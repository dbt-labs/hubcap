import json
import logging
from typing import List
from pathlib import Path

from hubcap.records import PackageMaintainer


class PackageMaintainerError(Exception):
    """Custom exception for package maintainer loading errors"""

    pass


def load_package_maintainers() -> List[PackageMaintainer]:
    """Hub's state determined by packages and their maintainers listed in hub.json"""
    try:
        # Check if required files exist
        hub_file = Path("hub.json")
        exclusions_file = Path("exclusions.json")

        if not hub_file.exists():
            raise PackageMaintainerError("hub.json file not found")

        if not exclusions_file.exists():
            logging.warning("exclusions.json file not found, using empty exclusions")
            excluded_pkgs_index = {}
        else:
            try:
                with open(exclusions_file, "r", encoding="utf-8") as excluded_stream:
                    excluded_pkgs_index = json.load(excluded_stream)
                    if not isinstance(excluded_pkgs_index, dict):
                        raise PackageMaintainerError(
                            "exclusions.json must contain a valid JSON object"
                        )
            except json.JSONDecodeError as e:
                raise PackageMaintainerError(
                    f"Invalid JSON in exclusions.json: {str(e)}"
                )
            except (OSError, IOError) as e:
                raise PackageMaintainerError(f"Error reading exclusions.json: {str(e)}")

        try:
            with open(hub_file, "r", encoding="utf-8") as hub_stream:
                org_pkg_index = json.load(hub_stream)
                if not isinstance(org_pkg_index, dict):
                    raise PackageMaintainerError(
                        "hub.json must contain a valid JSON object"
                    )
        except json.JSONDecodeError as e:
            raise PackageMaintainerError(f"Invalid JSON in hub.json: {str(e)}")
        except (OSError, IOError) as e:
            raise PackageMaintainerError(f"Error reading hub.json: {str(e)}")

        # Remove excluded dictionaries
        maintainer_index = {}
        for org, pkgs in org_pkg_index.items():
            try:
                if not isinstance(pkgs, list):
                    logging.warning(f"Invalid package list for {org}, skipping")
                    continue

                excluded_pkgs = excluded_pkgs_index.get(org, [])
                if not isinstance(excluded_pkgs, list):
                    logging.warning(f"Invalid exclusions for {org}, using empty list")
                    excluded_pkgs = []

                filtered_pkgs = set(pkgs) - set(excluded_pkgs)
                if filtered_pkgs:  # Only add maintainers with packages
                    maintainer_index[org] = filtered_pkgs
            except Exception as e:
                logging.warning(f"Error processing maintainer {org}: {str(e)}")
                continue

        return [
            PackageMaintainer(org_name, org_pkgs)
            for org_name, org_pkgs in maintainer_index.items()
        ]

    except Exception as e:
        if isinstance(e, PackageMaintainerError):
            raise
        raise PackageMaintainerError(
            f"Unexpected error loading package maintainers: {str(e)}"
        )
