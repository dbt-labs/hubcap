import hashlib
import os
import requests
import subprocess
import yaml

from pathlib import Path

from setup import *
from version import *


def has_dbt_project_yml(directory):
    return os.path.exists(directory / Path('dbt_project.yml'))


def parse_pkg_name(repo_dir):
    with open(repo_dir / Path('dbt_project.yml'), 'r') as stream:
        return yaml.safe_load(stream)['name']


def parse_pkgs(repo_dir):
    if os.path.exists(repo_dir / 'packages.yml'):
        with open(repo_dir / Path('packages.yml'), 'r') as stream:
            return yaml.safe_load(stream)['packages']


def cut_version_branch(org_name, repo, separate_commits_by_pkg):
    '''designed to be run in a hub repo which is sibling to package code repos'''

    if separate_commits_by_pkg:
        branch_name = f'bump-{org_name}-{repo}-{NOW}'
    else:
        branch_name = 'bump-{NOW}'

    logging.info(f'checking out branch {branch_name} in the hub repo itself')

    completed_subprocess = subprocess.run(['git', 'checkout', '-q', '-b', branch_name])
    if completed_subprocess.returncode == 128:
        run_cmd(f'git checkout -q {branch_name}')

    return branch_name


def fetch_index_file_contents(filepath):
    existing_index_file = {}

    if os.path.exists(filepath):
        with open(filepath, 'rb') as stream:
            existing_index_file_contents = stream.read().decode('utf-8').strip()
            try:
                existing_index_file = json.loads(existing_index_file_contents)
            except:
                pass

    return existing_index_file


def make_index(org_name, repo, package_name, existing, tags, git_path):
    description = "dbt models for {}".format(repo)
    assets = {
        "logo": "logos/placeholder.svg".format(repo)
    }

    if isinstance(existing, dict):
        description = existing.get('description', description)
        assets = existing.get('assets', assets)

    # attempt to grab the latest release version of a project

    version_numbers = [tag[1:] if tag.startswith('v') else tag for tag in tags]
    version_numbers.sort(key=lambda s: list(map(int, s.split('.'))))
    latest_version = version_numbers[-1]

    if not latest_version:
        latest_version = ''

    return {
        "name": package_name,
        "namespace": org_name,
        "description": description,
        "latest": latest_version.replace("=", ""), # LOL
        "assets": assets
    }


def download(url):
    response = requests.get(url)

    file_buf = b""
    for block in response.iter_content(1024*64):
        file_buf += block

    return file_buf


def get_sha1(url):
    print("    downloading: {}".format(url))
    contents = download(url)
    hasher = hashlib.sha1()
    hasher.update(contents)
    digest = hasher.hexdigest()
    print("      SHA1: {}".format(digest))
    return digest


def make_spec(org, repo, package_name, packages, version, git_path):
    tarball_url = "https://codeload.github.com/{}/{}/tar.gz/{}".format(org, repo, version)
    sha1 = get_sha1(tarball_url)

    # note: some packages do not have a packages.yml
    return {
        "id": "{}/{}/{}".format(org, package_name, version),
        "name": package_name,
        "version": version,
        "published_at": NOW_ISO,
        "packages": packages,
        "works_with": [],
        "_source": {
            "type": "github",
            "url": "https://github.com/{}/{}/tree/{}/".format(org, repo, version),
            "readme": "https://raw.githubusercontent.com/{}/{}/{}/README.md".format(org, repo, version)
        },
        "downloads": {
            "tarball": tarball_url,
            "format": "tgz",
            "sha1": sha1
        }
    }
