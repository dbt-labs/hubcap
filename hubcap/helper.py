"""Environment setup and state generation for hubcap"""

import datetime
import json
import logging
import os

from pathlib import Path
from records import PackageMaintainer

NOW = int(datetime.datetime.now().timestamp())

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


def build_config():
    """Pull the config env variable which holds github secrets"""
    return json.loads(os.environ["CONFIG"])


def load_package_maintainers():
    """Hub's state determined by packages and their maintainers listed in hub.json"""
    with open("hub.json", "r") as hub_stream, open(
        "exclusions.json"
    ) as excluded_stream:
        org_pkg_index = json.load(hub_stream)
        # Mila: we should strive to periodically remove dead packages from hub.json
        excluded_pkgs_index = json.load(excluded_stream)

    # Remove excluded dictionaries
    maintainer_index = {
        org: set(pkgs) - set(excluded_pkgs_index.get(org, []))
        for org, pkgs in org_pkg_index.items()
    }

    return [
        PackageMaintainer(org_name, org_pkgs)
        for org_name, org_pkgs in maintainer_index.items()
        if maintainer_index[org_name]
    ]


def build_pkg_version_index(hub_path):
    """traverse the hub repo and load all versions for every package of every org into memory"""

    # store previous path for easy return at function exit
    prev_path = os.getcwd()
    os.chdir(hub_path)

    maintainer_package_map = {
        maintainer: os.listdir(Path("data") / Path("packages") / Path(maintainer))
        for maintainer in os.listdir(Path("data") / Path("packages"))
    }

    package_version_index = {
        (package, maintainer): [
            # sublist of all versions checked into hub
            os.path.basename(f)[: -len(".json")]  # include semver in filename only
            for f in (Path("data") / "packages" / maintainer / package).glob("*/*.json")
        ]
        for maintainer in maintainer_package_map.keys()
        for package in maintainer_package_map[maintainer]
    }

    os.chdir(prev_path)
    return package_version_index
