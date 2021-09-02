import logging
import os
import re

from cmd import *
from package import *


def is_valid_semver_tag(tag):
    # regex taken from official SEMVER documentation site
    match = re.match('^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$',
        tag[1:] if tag.startswith('v') else tag
    )

    return match is not None and match.group('prerelease') is None


def strip_v_from_version(tag):
    if tag.startswith('v'):
        return tag[1:]
    else:
        return tag


def get_existing_tags(pkg_index_records):
    return { pkg_index_record['version'] for pkg_index_record in pkg_index_records }


def get_new_tags(pkg_index_records):
    '''designed to be run inside a package repo'''

    run_cmd('git fetch --quiet --tags')
    all_remote_tags = run_cmd('git tag --list', quiet=True).split('\n')
    valid_remote_tags = set(filter(is_valid_semver_tag, all_remote_tags))
    logging.info(f'remote tags: {sorted(valid_remote_tags)}')

    existing_tags = get_existing_tags(pkg_index_records)
    logging.info(f'hub tags:    {sorted(existing_tags)}')

    return valid_remote_tags - existing_tags
