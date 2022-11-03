'''Module for altering the state of a package repo'''

import logging
import os
import yaml

from git import Repo
from pathlib import Path

import records
import version

from setup import *


def clone_package_repos(package_maintainer_index, path):
    '''clone all package repos listed in index to path'''
    for maintainer in package_maintainer_index:
        for package in maintainer.get_packages():
            name = maintainer.get_name()
            current_repo_path = path / Path(f'{name}_{package}')

            logging.info(f'Drawing down {name}\'s {package}')
            clone_url = f'https://github.com/{name}/{package}.git'
            clone_repo(clone_url, current_repo_path)


def parse_pkg_name(repo_dir):
    with open(repo_dir / Path('dbt_project.yml'), 'r') as stream:
        name = yaml.safe_load(stream)['name']
        return name if name else ''


def parse_require_dbt_version(repo_dir):
    with open(repo_dir / Path('dbt_project.yml'), 'r') as stream:
        requirements = yaml.safe_load(stream).get('require-dbt-version', [])
        return requirements if requirements else []


def parse_pkgs(repo_dir):
    if os.path.exists(repo_dir / 'packages.yml'):
        with open(repo_dir / Path('packages.yml'), 'r') as stream:
            pkgs = yaml.safe_load(stream)['packages']
            return pkgs if pkgs else []
    else:
        return []


def get_update_tasks(maintainers, version_index, path):
    '''build list of tasks for package version-bump commits'''

    def has_dbt_project_yml(package, directory):
        '''Any package without a dbt_project.yml should be ignored'''
        has_yaml = os.path.exists(directory / Path('dbt_project.yml'))
        if not has_yaml:
            logging.warning(f'{package} has no dbt_project.yml. Skipping...')
        return has_yaml

    def get_new_tags(repo_path, maintainer_name):
        # Existing tags are fetched from version index
        yml_package_name = parse_pkg_name(repo_path)
        logging.info(f'collecting tags for {yml_package_name}')

        existing_tags = version.get_existing_tags(
            version_index.get((yml_package_name, maintainer_name), set())
        )
        logging.info(f'pkg hub tags:    {sorted(existing_tags)}')

        valid_remote_tags = version.get_valid_remote_tags(Repo(repo_path))
        logging.info(f'pkg remote tags: {sorted(valid_remote_tags)}')

        new_tags = list(valid_remote_tags - existing_tags)
        return yml_package_name, existing_tags, new_tags

    def build_update_task_tuple(maintainer_name, hub_package_name):
        SKIP = None
        repo_path = path / Path(f'{maintainer_name}_{hub_package_name}')

        # Cannot create update task for package without dbt_projects yaml
        if not has_dbt_project_yml(hub_package_name, repo_path):
            return SKIP

        yml_package_name, existing_tags, new_tags = get_new_tags(repo_path, maintainer_name)
        if new_tags:
            logging.info(f'creating task to add new tags {list(new_tags)} to {yml_package_name}')
            return records.UpdateTask(
                github_username=maintainer_name,
                github_repo_name=hub_package_name,
                local_path_to_repo=repo_path,
                package_name=yml_package_name,
                existing_tags=existing_tags,
                new_tags=new_tags
            )
        # Cannot create update task for package without new tags
        else:
            logging.info(f'no new tags for {yml_package_name}. Skipping...')
            return SKIP

    return [
        update_task for update_task in (
            build_update_task_tuple(maintainer.get_name(), package)
            for maintainer in maintainers
            for package in maintainer.get_packages()
        ) if update_task
    ]


def commit_version_updates_to_hub(tasks, hub_dir_path, pr_strategy, default_branch='main'):
    '''input: UpdateTask
    output: {branch_name: hashmap of branch info}
    N.B. this function will make changes to the local copy of hub only
    '''
    res = {}
    for task in tasks:
        # major side effect is to commit on a new branch package updates
        branch_name, org_name, package_name = task.run(hub_dir_path, pr_strategy)
        res[branch_name] = {"org": org_name, "repo": package_name}

        # good house keeping
        os.chdir(hub_dir_path)
        cmd = f'git checkout {default_branch}'
        run_cmd(cmd)
    return res
