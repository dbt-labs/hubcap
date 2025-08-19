"""Interface for objects useful to processing hub entries"""

import hashlib
import json
import logging
import os
import requests
import subprocess

from abc import ABC, abstractmethod
from pathlib import Path

from hubcap import git_helper
from hubcap import helper
from hubcap import package
from hubcap import version


def check_fusion_schema_compatibility(repo_path: Path) -> bool:
    """
    Check if a dbt package is fusion schema compatible by running 'dbtf parse'.

    Args:
        repo_path: Path to the dbt package repository

    Returns:
        True if fusion compatible (dbtf parse exits with code 0), False otherwise
    """
    # Add a test profiles.yml to the current directory
    profiles_path = repo_path / Path("profiles.yml")
    try:
        with open(profiles_path, "a") as f:
            f.write(
                "\n"
                "test_schema_compat:\n"
                "  target: dev\n"
                "  outputs:\n"
                "    dev:\n"
                "      type: postgres\n"
                "      host: localhost\n"
                "      port: 5432\n"
                "      user: postgres\n"
                "      password: postgres\n"
                "      dbname: postgres\n"
                "      schema: public\n"
            )

        # Ensure the `_DBT_FUSION_STRICT_MODE` is set (this will ensure fusion errors on schema violations)
        os.environ["_DBT_FUSION_STRICT_MODE"] = "1"

        # Run dbtf parse command (try dbtf first, fall back to dbt)
        try:
            # Try dbtf first (without shell=True to get proper FileNotFoundError)
            result = subprocess.run(
                [
                    "dbtf",
                    "parse",
                    "--profile",
                    "test_schema_compat",
                    "--project-dir",
                    str(repo_path),
                ],
                capture_output=True,
                timeout=60,
            )
            # If dbtf command exists but returns error mentioning it's not found, fall back to dbt
            if (
                result.returncode != 0
                and result.stderr
                and b"not found" in result.stderr
            ):
                raise FileNotFoundError("dbtf command not found")
        except FileNotFoundError:
            # Fall back to dbt command, but validate that this is dbt-fusion
            version_result = subprocess.run(
                ["dbt", "--version"], capture_output=True, timeout=60
            )
            if b"dbt-fusion" not in version_result.stdout:
                raise FileNotFoundError(
                    "dbt-fusion command not found - regular dbt-core detected instead"
                )

            # Run dbt parse since we have dbt-fusion
            result = subprocess.run(
                [
                    "dbt",
                    "parse",
                    "--profile",
                    "test_schema_compat",
                    "--project-dir",
                    str(repo_path),
                ],
                capture_output=True,
                timeout=60,
            )

        # Return True if exit code is 0 (success)
        is_compatible = result.returncode == 0

        if is_compatible:
            logging.info(f"Package at {repo_path} is fusion schema compatible")
        else:
            logging.info(f"Package at {repo_path} is not fusion schema compatible")

        # Remove the test profile
        os.remove(profiles_path)

        return is_compatible

    except subprocess.TimeoutExpired:
        logging.warning(f"dbtf parse timed out for package at {repo_path}")
        try:
            os.remove(profiles_path)
        except Exception:
            pass
        return False
    except FileNotFoundError:
        logging.warning(
            f"dbtf command not found - skipping fusion compatibility check for {repo_path}"
        )
        try:
            os.remove(profiles_path)
        except Exception:
            pass
        return False
    except Exception as e:
        logging.warning(
            f"Error checking fusion compatibility for {repo_path}: {str(e)}"
        )
        try:
            os.remove(profiles_path)
        except Exception:
            pass
        return False


class PullRequestStrategy(ABC):
    @abstractmethod
    def pull_request_title(self, org: str, repo: str) -> str:
        pass

    @abstractmethod
    def branch_name(self, org: str, repo: str) -> str:
        pass


class IndividualPullRequests(PullRequestStrategy):
    def pull_request_title(self, org: str, repo: str) -> str:
        return f"hubcap: Bump {org}/{repo}"

    def branch_name(self, org: str, repo: str) -> str:
        return f"bump-{org}-{repo}-{helper.NOW}"


class ConsolididatedPullRequest(PullRequestStrategy):
    def pull_request_title(self, org: str, repo: str) -> str:
        return "hubcap: Bump package versions"

    def branch_name(self, org: str, repo: str) -> str:
        return f"bump-package-versions-{helper.NOW}"


class PackageMaintainer(object):
    def __init__(self, name: str, all_pkgs: object):
        self.name = name
        self.packages = set(all_pkgs)

    def get_name(self):
        return self.name

    def get_packages(self):
        return self.packages

    def __str__(self):
        return f"(maintainer: {self.name}, packages: {self.packages})"

    def __eq__(self, other):
        return (
            self.get_name() == other.get_name()
            and self.get_packages() == self.get_packages()
        )


class UpdateTask(object):
    def __init__(
        self,
        github_username: str,
        github_repo_name: str,
        local_path_to_repo: Path,
        package_name: str,
        existing_tags: list,
        new_tags: list,
        hub_repo: str,
    ):
        self.github_username = github_username
        self.github_repo_name = github_repo_name
        self.hub_version_index_path = (
            Path(os.path.dirname(local_path_to_repo))
            / hub_repo
            / "data"
            / "packages"
            / github_username
            / package_name
            / "versions"
        )
        self.local_path_to_repo = local_path_to_repo
        self.package_name = package_name
        self.existing_tags = existing_tags
        self.new_tags = new_tags
        # Track fusion compatibility for each tag
        self.fusion_compatibility = {}

    def run(self, main_dir, pr_strategy):
        os.chdir(main_dir)
        # Ensure versions directory for a hub package entry
        Path.mkdir(self.hub_version_index_path, parents=True, exist_ok=True)

        branch_name = self.cut_version_branch(pr_strategy)

        # create an updated version of the repo's index.json
        index_filepath = (
            Path(os.path.dirname(self.hub_version_index_path)) / "index.json"
        )

        # create a version spec for each tag
        for tag in self.new_tags:
            # go to repo dir to checkout tag and tag-commit specific package list
            os.chdir(self.local_path_to_repo)
            git_helper.run_cmd(f"git checkout tags/{tag}")
            packages = package.parse_pkgs(Path(os.getcwd()))
            require_dbt_version = package.parse_require_dbt_version(Path(os.getcwd()))
            os.chdir(main_dir)

            # check fusion compatibility
            is_fusion_compatible = check_fusion_schema_compatibility(
                self.local_path_to_repo
            )
            self.fusion_compatibility[tag] = is_fusion_compatible

            # Reset and clean the repo to ensure clean state after fusion check
            os.chdir(self.local_path_to_repo)
            git_helper.run_cmd("git reset --hard HEAD")
            git_helper.run_cmd("git clean -fd")
            os.chdir(main_dir)

            # return to hub and build spec
            package_spec = self.make_spec(
                self.github_username,
                self.github_repo_name,
                self.package_name,
                packages,
                require_dbt_version,
                tag,
                is_fusion_compatible,
            )

            version_path = self.hub_version_index_path / Path(f"{tag}.json")
            with open(version_path, "w") as f:
                logging.info(f"writing spec to {version_path}")
                f.write(str(json.dumps(package_spec, indent=4)))

            msg = f"hubcap: Adding tag {tag} for {self.github_username}/{self.github_repo_name}"
            logging.info(msg)
            git_helper.run_cmd("git add -A")
            subprocess.run(args=["git", "commit", "-am", f"{msg}"], capture_output=True)

        new_index_entry = self.make_index(
            self.github_username,
            self.github_repo_name,
            self.package_name,
            self.fetch_index_file_contents(index_filepath),
            set(self.new_tags) | set(self.existing_tags),
            self.fusion_compatibility,
        )
        with open(index_filepath, "w") as f:
            logging.info(f"writing index.json to {index_filepath}")
            f.write(str(json.dumps(new_index_entry, indent=4)))

        # Commit the updated index.json file
        msg = f"hubcap: Update index.json for {self.github_username}/{self.github_repo_name}"
        logging.info(msg)
        git_helper.run_cmd("git add -A")
        subprocess.run(args=["git", "commit", "-am", f"{msg}"], capture_output=True)

        # if successful return branchname
        return branch_name, self.github_username, self.github_repo_name

    def cut_version_branch(self, pr_strategy):
        """designed to be run in a hub repo which is sibling to package code repos"""
        branch_name = pr_strategy.branch_name(
            self.github_username, self.github_repo_name
        )
        helper.logging.info(f"checking out branch {branch_name} in the hub repo")

        completed_subprocess = subprocess.run(
            ["git", "checkout", "-q", "-b", branch_name]
        )
        if completed_subprocess.returncode == 128:
            git_helper.run_cmd(f"git checkout -q {branch_name}")

        return branch_name

    def make_index(
        self, org_name, repo, package_name, existing, tags, fusion_compatibility
    ):
        description = "dbt models for {}".format(repo)
        assets = {"logo": "logos/placeholder.svg"}

        if isinstance(existing, dict):
            description = existing.get("description", description)
            assets = existing.get("assets", assets)

        # attempt to grab the latest final version of a project if one exists
        # (and the latest prerelease otherwise)
        latest_version = version.latest_version(tags)

        return {
            "name": package_name,
            "namespace": org_name,
            "description": description,
            "latest": latest_version.replace("=", ""),  # LOL
            "latest-fusion-schema-compat": fusion_compatibility.get(
                latest_version, False
            ),
            "assets": assets,
        }

    def fetch_index_file_contents(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, "rb") as stream:
                existing_index_file_contents = stream.read().decode("utf-8").strip()
                try:
                    return json.loads(existing_index_file_contents)
                except Exception:
                    return {}

    def download(self, url):
        """Get some content to create a sha (very surely) unique to that package version"""
        response = requests.get(url)
        response.raise_for_status()

        file_buf = b""
        for block in response.iter_content(1024 * 64):
            file_buf += block

        return file_buf

    def get_sha1(self, url):
        """used to create a unique sha for each release"""
        logging.info(f"    downloading: {url}")
        contents = self.download(url)
        hasher = hashlib.sha1()
        hasher.update(contents)
        digest = hasher.hexdigest()
        logging.info(f"      SHA1: {digest}")
        return digest

    def make_spec(
        self,
        org,
        repo,
        package_name,
        packages,
        require_dbt_version,
        version,
        fusion_schema_compat=False,
    ):
        """The hub needs these specs for packages to be discoverable by deps and on the web"""
        tarball_url = "https://codeload.github.com/{}/{}/tar.gz/{}".format(
            org, repo, version
        )
        sha1 = self.get_sha1(tarball_url)

        # note: some packages do not have a packages.yml
        return {
            "id": "{}/{}/{}".format(org, package_name, version),
            "name": package_name,
            "version": version,
            "published_at": "1970-01-01T00:00:00.000000+00:00",
            "packages": packages,
            "require_dbt_version": require_dbt_version,
            "works_with": [],
            "_source": {
                "type": "github",
                "url": "https://github.com/{}/{}/tree/{}/".format(org, repo, version),
                "readme": "https://raw.githubusercontent.com/{}/{}/{}/README.md".format(
                    org, repo, version
                ),
            },
            "downloads": {"tarball": tarball_url, "format": "tgz", "sha1": sha1},
            "fusion-schema-compat": fusion_schema_compat,
        }
