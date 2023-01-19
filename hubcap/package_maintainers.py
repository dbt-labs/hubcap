import json

from hubcap.records import PackageMaintainer


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
