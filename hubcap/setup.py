import collections
import datetime
import json
import logging
import os
import re
import requests

from pathlib import Path

NOW = int(datetime.datetime.now().timestamp())
NOW_ISO = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

def build_config():
    config = json.loads(os.environ['CONFIG'])
    config['tracked_repos'] = {}

    with open('hub.json', 'r') as hub_stream, open('exclusions.json') as excluded_stream:
        org_pkg_list = json.load(hub_stream)
        # Mila: eventually we instead remove the packages at their source rather than this post-facto filtering
        excluded_pkg_list = json.load(excluded_stream)

        for org_name, org_pkg_names in org_pkg_list.items():
            res_pkg_list = [pkg_name for pkg_name in org_pkg_names
                if not (org_name in excluded_pkg_list.keys() and pkg_name in excluded_pkg_list[org_name])
            ]

            if res_pkg_list:
                config['tracked_repos'][org_name] = res_pkg_list

    return config


def build_version_index():
    index = collections.defaultdict(lambda : collections.defaultdict(list))
    pkg_version_indexes = [ filepath for filepath in (Path('data') / Path('packages')).glob('**/*.json')
                        if os.path.basename(filepath) != 'index.json' ]

    for path in pkg_version_indexes:
        org_name, repo_name = re.match(r'data/packages/(.+)/(.+)/versions', str(path)).groups()
        info = {"path": path, "version": os.path.basename(path)[:-len('.json')]}
        index[org_name][repo_name].append(info)

    return index
