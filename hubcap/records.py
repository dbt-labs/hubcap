"""Interface for objects useful to processing hub entries"""

from typing import Optional
from dbt_fusion_package_tools.compatibility import FusionConformanceResult
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

    def run(self, main_dir, pr_strategy):
        os.chdir(main_dir)
        # Ensure versions directory for a hub package entry
        Path.mkdir(self.hub_version_index_path, parents=True, exist_ok=True)

        branch_name = self.cut_version_branch(pr_strategy)

        # create an updated version of the repo's index.json
        index_filepath = (
            Path(os.path.dirname(self.hub_version_index_path)) / "index.json"
        )
        new_index_entry = self.make_index(
            self.github_username,
            self.github_repo_name,
            self.package_name,
            self.fetch_index_file_contents(index_filepath),
            set(self.new_tags) | set(self.existing_tags),
        )
        with open(index_filepath, "w") as f:
            logging.info(f"writing index.json to {index_filepath}")
            f.write(str(json.dumps(new_index_entry, indent=4)))

        # create a version spec for each tag
        for tag in self.new_tags:
            # go to repo dir to checkout tag and tag-commit specific package list
            os.chdir(self.local_path_to_repo)
            git_helper.run_cmd(f"git checkout tags/{tag}")
            packages = package.parse_pkgs(Path(os.getcwd()))
            require_dbt_version = package.parse_require_dbt_version(Path(os.getcwd()))

            # return to hub and build spec
            os.chdir(main_dir)
            package_spec = self.make_spec(
                self.github_username,
                self.github_repo_name,
                self.package_name,
                packages,
                require_dbt_version,
                tag,
            )

            version_path = self.hub_version_index_path / Path(f"{tag}.json")
            with open(version_path, "w") as f:
                logging.info(f"writing spec to {version_path}")
                f.write(str(json.dumps(package_spec, indent=4)))

            msg = f"hubcap: Adding tag {tag} for {self.github_username}/{self.github_repo_name}"
            logging.info(msg)
            git_helper.run_cmd("git add -A")
            subprocess.run(args=["git", "commit", "-am", f"{msg}"], capture_output=True)

        # if succesful return branchname
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

    def make_index(self, org_name, repo, package_name, existing, tags):
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
        self, org, repo, package_name, packages, require_dbt_version, version, conformance_output: Optional[FusionConformanceResult]=None
    ):
        """The hub needs these specs for packages to be discoverable by deps and on the web"""
        tarball_url = "https://codeload.github.com/{}/{}/tar.gz/{}".format(
            org, repo, version
        )
        sha1 = self.get_sha1(tarball_url)

        # note: some packages do not have a packages.yml
        spec = {
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
        }
        if conformance_output is not None:
            spec["fusion_compatibility"] = conformance_output.to_dict()
        return spec
