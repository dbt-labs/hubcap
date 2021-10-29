'''Environment setup and state generation for hubcap'''

import collections
import datetime
import json
import logging
import os
import re
import requests

from pathlib import Path
from cmd import *

NOW = int(datetime.datetime.now().timestamp())
NOW_ISO = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

def build_config():
    '''Pull the config env variable which holds github secrets'''
    return json.loads(os.environ['CONFIG'])

def load_tracked_repo_records():
    '''Determine hub's current state by accessing repo's tracking directory'''
    res = {}
    with open('hub.json', 'r') as hub_stream, open('exclusions.json') as excluded_stream:
        org_pkg_list = json.load(hub_stream)
        # Mila: eventually we should instead remove the packages at their source rather than this post-facto filtering
        excluded_pkg_list = json.load(excluded_stream)

        for org_name, org_pkg_names in org_pkg_list.items():
            res_pkg_list = [pkg_name for pkg_name in org_pkg_names
                if not (org_name in excluded_pkg_list.keys() and pkg_name in excluded_pkg_list[org_name])
            ]

            if res_pkg_list:
                res[org_name] = res_pkg_list
    return res


def build_pkg_version_index(hub_path):
    '''traverse the hub repo and load all versions for every package of every org into memory'''
    prev_path = os.getcwd()
    os.chdir(hub_path)
    index = collections.defaultdict(lambda : collections.defaultdict(list))
    pkg_version_indexes = [ filepath for filepath in (Path('data') / Path('packages')).glob('**/*.json')
                        if os.path.basename(filepath) != 'index.json' ]

    for path in pkg_version_indexes:
        org_name, repo_name = re.match(r'data/packages/(.+)/(.+)/versions', str(path)).groups()
        index[org_name][repo_name].append(os.path.basename(path)[:-len('.json')])

    os.chdir(prev_path)
    return index
