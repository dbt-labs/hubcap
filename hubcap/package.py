"""Module for altering the state of a package repo"""

import logging
import os
import yaml
from typing import List, Dict, Any

from git import Repo
from pathlib import Path

from hubcap import records
from hubcap import version
from hubcap.git_helper import clone_repo, run_cmd, GitOperationError


class PackageError(Exception):
    """Custom exception for package operation failures"""

    pass


def clone_package_repos(package_maintainer_index, path):
    """clone all package repos listed in index to path"""
    failed_repos = []

    for maintainer in package_maintainer_index:
        for package in maintainer.get_packages():
            name = maintainer.get_name()
            current_repo_path = path / Path(f"{name}_{package}")

            logging.info(f"Drawing down {name}'s {package}")
            clone_url = f"https://github.com/{name}/{package}.git"

            try:
                clone_repo(clone_url, current_repo_path)
            except GitOperationError as e:
                logging.error(f"Failed to clone {name}/{package}: {str(e)}")
                failed_repos.append(f"{name}/{package}")
                continue
            except Exception as e:
                logging.error(f"Unexpected error cloning {name}/{package}: {str(e)}")
                failed_repos.append(f"{name}/{package}")
                continue

    if failed_repos:
        logging.warning(
            f"Failed to clone {len(failed_repos)} repositories: {', '.join(failed_repos)}"
        )

    return failed_repos


def parse_pkg_name(repo_dir) -> str:
    """Parse package name from dbt_project.yml with error handling"""
    try:
        dbt_project_path = repo_dir / Path("dbt_project.yml")
        if not dbt_project_path.exists():
            raise PackageError(f"dbt_project.yml not found in {repo_dir}")

        with open(dbt_project_path, "r", encoding="utf-8") as stream:
            try:
                config = yaml.safe_load(stream)
                if not config:
                    raise PackageError(
                        f"Empty or invalid dbt_project.yml in {repo_dir}"
                    )

                name = config.get("name")
                if not name:
                    raise PackageError(
                        f"No 'name' field found in dbt_project.yml in {repo_dir}"
                    )

                return name
            except yaml.YAMLError as e:
                raise PackageError(
                    f"Invalid YAML in dbt_project.yml in {repo_dir}: {str(e)}"
                )
    except (OSError, IOError) as e:
        raise PackageError(f"Error reading dbt_project.yml in {repo_dir}: {str(e)}")
    except Exception as e:
        raise PackageError(
            f"Unexpected error parsing package name from {repo_dir}: {str(e)}"
        )


def parse_require_dbt_version(repo_dir) -> List[str]:
    """Parse required dbt version from dbt_project.yml with error handling"""
    try:
        dbt_project_path = repo_dir / Path("dbt_project.yml")
        if not dbt_project_path.exists():
            logging.warning(
                f"dbt_project.yml not found in {repo_dir}, using empty requirements"
            )
            return []

        with open(dbt_project_path, "r", encoding="utf-8") as stream:
            try:
                config = yaml.safe_load(stream)
                if not config:
                    logging.warning(
                        f"Empty dbt_project.yml in {repo_dir}, using empty requirements"
                    )
                    return []

                requirements = config.get("require-dbt-version", [])
                return requirements if requirements else []
            except yaml.YAMLError as e:
                logging.warning(
                    f"Invalid YAML in dbt_project.yml in {repo_dir}: {str(e)}, using empty requirements"
                )
                return []
    except (OSError, IOError) as e:
        logging.warning(
            f"Error reading dbt_project.yml in {repo_dir}: {str(e)}, using empty requirements"
        )
        return []
    except Exception as e:
        logging.warning(
            f"Unexpected error parsing dbt version requirements from {repo_dir}: {str(e)}, using empty requirements"
        )
        return []


def parse_pkgs(repo_dir) -> List[Dict[str, Any]]:
    """Parse packages.yml or dependencies.yml with error handling"""
    try:
        # Check for packages.yml first
        if os.path.exists(repo_dir / "packages.yml"):
            with open(repo_dir / Path("packages.yml"), "r", encoding="utf-8") as stream:
                try:
                    pkgs = yaml.safe_load(stream)
                    return pkgs.get("packages", []) if pkgs else []
                except yaml.YAMLError as e:
                    logging.warning(
                        f"Invalid YAML in packages.yml in {repo_dir}: {str(e)}"
                    )
                    return []

        # Check for dependencies.yml (new in v1.6)
        elif os.path.exists(repo_dir / "dependencies.yml"):
            with open(
                repo_dir / Path("dependencies.yml"), "r", encoding="utf-8"
            ) as stream:
                try:
                    pkgs = yaml.safe_load(stream)
                    return pkgs.get("packages", []) if pkgs else []
                except yaml.YAMLError as e:
                    logging.warning(
                        f"Invalid YAML in dependencies.yml in {repo_dir}: {str(e)}"
                    )
                    return []
        else:
            return []
    except (OSError, IOError) as e:
        logging.warning(f"Error reading package files in {repo_dir}: {str(e)}")
        return []
    except Exception as e:
        logging.warning(f"Unexpected error parsing packages from {repo_dir}: {str(e)}")
        return []


def get_update_tasks(maintainers, version_index, path, hub_repo):
    """build list of tasks for package version-bump commits"""

    def has_dbt_project_yml(package, directory):
        """Any package without a dbt_project.yml should be ignored"""
        has_yaml = os.path.exists(directory / Path("dbt_project.yml"))
        if not has_yaml:
            logging.warning(f"{package} has no dbt_project.yml. Skipping...")
        return has_yaml

    def get_new_tags(repo_path, maintainer_name):
        # Existing tags are fetched from version index
        try:
            yml_package_name = parse_pkg_name(repo_path)
            logging.info(f"collecting tags for {yml_package_name}")

            existing_tags = version.get_existing_tags(
                version_index.get((yml_package_name, maintainer_name), set())
            )
            logging.info(f"pkg hub tags:    {sorted(existing_tags)}")

            valid_remote_tags = version.get_valid_remote_tags(Repo(repo_path))
            logging.info(f"pkg remote tags: {sorted(valid_remote_tags)}")

            new_tags = list(valid_remote_tags - existing_tags)
            return yml_package_name, existing_tags, new_tags
        except PackageError as e:
            logging.error(f"Error getting tags for {repo_path}: {str(e)}")
            return None, set(), []
        except Exception as e:
            logging.error(f"Unexpected error getting tags for {repo_path}: {str(e)}")
            return None, set(), []

    def build_update_task_tuple(maintainer_name, hub_package_name):
        SKIP = None
        repo_path = path / Path(f"{maintainer_name}_{hub_package_name}")

        # Check if repo directory exists
        if not repo_path.exists():
            logging.warning(f"Repository directory not found: {repo_path}. Skipping...")
            return SKIP

        # Cannot create update task for package without dbt_projects yaml
        if not has_dbt_project_yml(hub_package_name, repo_path):
            return SKIP

        try:
            yml_package_name, existing_tags, new_tags = get_new_tags(
                repo_path, maintainer_name
            )

            if yml_package_name is None:
                return SKIP

            if new_tags:
                logging.info(
                    f"creating task to add new tags {list(new_tags)} to {yml_package_name}"
                )
                return records.UpdateTask(
                    github_username=maintainer_name,
                    github_repo_name=hub_package_name,
                    local_path_to_repo=repo_path,
                    package_name=yml_package_name,
                    existing_tags=existing_tags,
                    new_tags=new_tags,
                    hub_repo=hub_repo,
                )
            # Cannot create update task for package without new tags
            else:
                logging.info(f"no new tags for {yml_package_name}. Skipping...")
                return SKIP
        except Exception as e:
            logging.error(
                f"Error building update task for {maintainer_name}/{hub_package_name}: {str(e)}"
            )
            return SKIP

    return [
        update_task
        for update_task in (
            build_update_task_tuple(maintainer.get_name(), package)
            for maintainer in maintainers
            for package in maintainer.get_packages()
        )
        if update_task
    ]


def commit_version_updates_to_hub(
    tasks, hub_dir_path, pr_strategy, default_branch="main"
):
    """input: UpdateTask
    output: {branch_name: hashmap of branch info}
    N.B. this function will make changes to the local copy of hub only
    """
    res = {}
    failed_tasks = []

    for task in tasks:
        try:
            # major side effect is to commit on a new branch package updates
            branch_name, org_name, package_name = task.run(hub_dir_path, pr_strategy)
            res[branch_name] = {"org": org_name, "repo": package_name}

            # good house keeping
            os.chdir(hub_dir_path)
            cmd = f"git checkout {default_branch}"
            run_cmd(cmd)
        except Exception as e:
            logging.error(
                f"Failed to commit version updates for {task.package_name}: {str(e)}"
            )
            failed_tasks.append(f"{task.github_username}/{task.github_repo_name}")
            continue

    if failed_tasks:
        logging.warning(
            f"Failed to commit updates for {len(failed_tasks)} packages: {', '.join(failed_tasks)}"
        )

    return res
