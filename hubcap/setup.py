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

PKG_EXCLUSION_OVERRIDES = {
    'dbt-labs': ['bing-ads', 'recurly', 'shopify', 'purecloud', 'zendesk', 'stripe', 'outbrain', 'taboola',
                 'quickbooks', 'bing-ads', 'taboola', 'heap', 'ecommerce', 'facebook-ads', 'zendesk', 'stripe',
                 'purecloud'],
    'beautypie': ['dbt-google-analytics-360', 'dbt-zendesk-support']
}


def build_config():
    config = json.loads(os.environ['CONFIG'])
    config['tracked_repos'] = {}

    # necessary for as long as hubcap's git is disconnected from the github copy of the hub
    response = requests.get('https://raw.githubusercontent.com/dbt-labs/hubcap/master/hub.json')
    response.raise_for_status()
    org_pkg_list = response.json()

    for org_name, org_pkg_names in org_pkg_list.items():
        res_pkg_list = [pkg_name for pkg_name in org_pkg_names
            if not (org_name in PKG_EXCLUSION_OVERRIDES.keys() and pkg_name in PKG_EXCLUSION_OVERRIDES[org_name])
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
