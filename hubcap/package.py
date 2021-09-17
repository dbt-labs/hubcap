import hashlib
import os
import requests
import subprocess
import yaml

from git import cmd
from git import Repo
from pathlib import Path

import version

from setup import *


def has_dbt_project_yml(directory):
    return os.path.exists(directory / Path('dbt_project.yml'))


def clone_package_repos(repo_index, path):
    '''clone all package repos listed in index to path'''
    for org_name, repos in repo_index.items():
        for repo in repos:
            current_repo_path = path / Path(repo)

            logging.info(f'cloning package {repo} maintained by {org_name} to {current_repo_path}')
            clone_repo(f'https://github.com/{org_name}/{repo}.git', current_repo_path)

            # debugging for time
            return


def get_pkgs_with_updates(repo_index, version_index, path):
    '''obtain a sublist of the existing repo_index: all those packages with updates'''

    def parse_pkg_name(repo_dir):
        with open(repo_dir / Path('dbt_project.yml'), 'r') as stream:
            name = yaml.safe_load(stream)['name']
            return name if name else ''

    def parse_pkgs(repo_dir):
        if os.path.exists(repo_dir / 'packages.yml'):
            with open(repo_dir / Path('packages.yml'), 'r') as stream:
                pkgs = yaml.safe_load(stream)['packages']
                return pkgs if pkgs else []
        else:
            return []

    res = {}
    for org_name, repos in repo_index.items():
        for repo in repos:
            current_repo_path = path / Path(repo)

            if has_dbt_project_yml(current_repo_path):
                package_name = parse_pkg_name(current_repo_path)
                packages = parse_pkgs(current_repo_path)
                logging.info(f'collecting tags for {package_name}')

                existing_tags = version.get_existing_tags(version_index[org_name][package_name])
                logging.info(f'pkg hub tags:    {sorted(existing_tags)}')

                valid_remote_tags = version.get_valid_remote_tags(Repo(current_repo_path))
                logging.info(f'pkg remote tags: {sorted(valid_remote_tags)}')

                new_tags = list(valid_remote_tags - existing_tags) + ['0.7.2'] # TODO remove this
                if new_tags:
                    logging.info(f'adding new tags {list(new_tags)} to {package_name} repo')
                    if org_name not in res:
                        res[org_name] = {}
                    res[org_name][repo] = (package_name, current_repo_path, new_tags)
            else:
                logging.warning(f'{repo} has no dbt_project.yml. Skipping...')
    return res


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

    version_numbers = [version.strip_v_from_version(tag) for tag in tags]
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

def commit_version_updates_to_hub(new_pkg_version_index, hub_dir_path):
    '''input: {org_name: {repo_name:(package_name, [version tags])}}
    output: {branch_name: hashmap of branch info}
    N.B. this function will make changes to the hub only
    '''
    for org_name, new_repo_tags in new_pkg_version_index.items():
        for repo, (package_name, current_repo_path, new_tags) in new_repo_tags.items():
            os.chdir(hub_dir_path)
            repo_hub_version_dir = hub_dir_path / 'data' / 'packages' / org_name / package_name / 'versions'
            Path.mkdir(repo_hub_version_dir, parents=True, exist_ok=True)

            # in hub, on a branch for each package, commit the package version specs for any new tags
            branch_name = cut_version_branch(org_name, repo, ONE_BRANCH_PER_REPO)
            new_branches[branch_name] = {"org": org_name, "repo": package_name}

            # create an updated version of the repo's index.json
            index_file_path = hub_dir_path / 'data' / 'packages' / org_name / package_name / 'index.json'

            new_index_entry = make_index(
                org_name,
                repo,
                package_name,
                package.fetch_index_file_contents(index_file_path),
                set(new_tags) | version.get_existing_tags(existing_pkg_version_index[org_name][repo]),
                current_repo_path
            )

            with open(index_file_path, 'w') as f:
                logging.info(f'writing index.json to {index_file_path}')
                f.write(str(json.dumps(new_index_entry, indent=4)))

            # create a version spec for each tag
            for tag in new_tags:
                # TODO: patch in the code to get packages from each tag
                package_spec = make_spec(org_name, repo, package_name, packages, tag, current_repo_path)

                version_path = repo_hub_version_dir / Path(f'{tag}.json')

                with open(version_path, 'w') as f:
                    logging.info(f'writing spec to {version_path}')
                    f.write(str(json.dumps(package_spec, indent=4)))

                msg = f'hubcap: Adding tag {tag} for {org_name}/{repo}'
                logging.info(msg)
                run_cmd('git add -A')
                subprocess.run(args=['git', 'commit', '-am', f'{msg}'], capture_output=True)
                new_branches[branch_name]['new'] = True

            # good house keeping
            os.chdir(hub_dir_path)
            run_cmd('git checkout master')
