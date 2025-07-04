"""Interface for dispatching updates to packages back to github"""

import json
import logging
import requests
from typing import List, Tuple

from git import Repo
from git.remote import Remote
from git.exc import GitCommandError


class ReleaseCarrierError(Exception):
    """Custom exception for release carrier operation failures"""

    pass


def make_pr(org, repo, head, user_creds, url, pr_strategy, base="main"):
    """Create POST content which in turns create a hub new-version PR"""
    try:
        user = user_creds.get("name")
        token = user_creds.get("token")

        if not user or not token:
            raise ReleaseCarrierError("Missing user credentials (name or token)")

        title = pr_strategy.pull_request_title(org, repo)
        body = (
            "Auto-bumping from new release at https://github.com/{}/{}/releases".format(
                org, repo
            )
        )
        maintainer_can_modify = True
        post_pr(title, head, base, body, maintainer_can_modify, user, token, url)
    except Exception as e:
        if isinstance(e, ReleaseCarrierError):
            raise
        raise ReleaseCarrierError(
            f"Error creating pull request for {org}/{repo}: {str(e)}"
        )


def post_pr(title, head, base, body, maintainer_can_modify, user, token, url):
    """Create POST content which in turns create a hub new-version PR"""
    try:
        pr_body = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "maintainer_can_modify": maintainer_can_modify,
        }
        json_body = json.dumps(pr_body)

        response = requests.post(
            url,
            data=json_body,
            headers={"Content-Type": "application/json"},
            auth=(user, token),
            timeout=30,
        )
        response.raise_for_status()

        logging.info(f"Successfully created pull request: {title}")

    except requests.exceptions.Timeout:
        raise ReleaseCarrierError(f"Timeout creating pull request: {title}")
    except requests.exceptions.RequestException as e:
        if response.status_code == 422:
            raise ReleaseCarrierError(
                f"Pull request already exists or invalid: {title}"
            )
        elif response.status_code == 403:
            raise ReleaseCarrierError(
                f"Permission denied creating pull request: {title}"
            )
        elif response.status_code == 404:
            raise ReleaseCarrierError(f"Repository not found for pull request: {title}")
        else:
            raise ReleaseCarrierError(
                f"HTTP error creating pull request: {response.status_code} - {str(e)}"
            )
    except json.JSONDecodeError as e:
        raise ReleaseCarrierError(f"Error serializing pull request data: {str(e)}")
    except Exception as e:
        raise ReleaseCarrierError(f"Unexpected error creating pull request: {str(e)}")


def get_open_pr_titles(org_name, package_name, user_creds) -> List[str]:
    """Prevents opening duplicate PRs for currently open versions"""
    try:
        url = f"https://api.github.com/repos/{org_name}/{package_name}/pulls?state=open"

        user = user_creds.get("name")
        token = user_creds.get("token")

        if not user or not token:
            logging.warning(
                "Missing credentials for checking open PRs, assuming none exist"
            )
            return []

        pr_titles = []

        response = requests.get(url, auth=(user, token), timeout=30)
        response.raise_for_status()
        pr_titles = [pr["title"] for pr in response.json()]

        return pr_titles

    except requests.exceptions.Timeout:
        logging.warning(f"Timeout checking open PRs for {org_name}/{package_name}")
        return []
    except requests.exceptions.RequestException as e:
        if response.status_code == 404:
            logging.warning(
                f"Repository {org_name}/{package_name} not found when checking PRs"
            )
        elif response.status_code == 403:
            logging.warning(
                f"Permission denied checking PRs for {org_name}/{package_name}"
            )
        else:
            logging.warning(
                f"Error checking open PRs for {org_name}/{package_name}: {str(e)}"
            )
        return []
    except Exception as e:
        logging.warning(
            f"Unexpected error checking open PRs for {org_name}/{package_name}: {str(e)}"
        )
        return []


def is_open_pr(prs, org_name, pkg_name):
    """Check if a PR is already open for the given org and package"""
    try:
        return any("{}/{}".format(org_name, pkg_name) in pr for pr in prs)
    except Exception as e:
        logging.warning(
            f"Error checking if PR is open for {org_name}/{pkg_name}: {str(e)}"
        )
        return False


def get_org_repo(remote_url: str) -> Tuple[str, str]:
    """Parse the organization and repository from a GitHub remote URL."""
    try:
        if not remote_url:
            raise ReleaseCarrierError("Remote URL is required")

        parts = remote_url.split("/")
        if len(parts) < 2:
            raise ReleaseCarrierError(f"Invalid remote URL format: {remote_url}")

        target_org = parts[-2]
        target_pkg = parts[-1]

        # Strip off "git@github.com:" from the beginning of the organization name
        target_org = target_org.replace("git@github.com:", "")
        # Strip off ".git" from the end of the package name
        target_pkg_name = (
            target_pkg[: -len(".git")] if target_pkg.endswith(".git") else target_pkg
        )

        return target_org, target_pkg_name
    except Exception as e:
        if isinstance(e, ReleaseCarrierError):
            raise
        raise ReleaseCarrierError(f"Error parsing remote URL '{remote_url}': {str(e)}")


def open_new_prs(
    target_repo_path,
    remote_url,
    branches,
    user_creds,
    push_branches,
    pull_request_url,
    pr_strategy,
    default_branch="main",
):
    """Expects: {branch_name: hashmap of branch info} and {user_name, access token}
    will push prs up to a github remote"""

    try:
        if not branches:
            logging.info("No branches to process")
            return

        target_repo = Repo(target_repo_path)

        # Ensure hub remote exists
        try:
            if not Remote(target_repo, "hub").exists():
                target_repo.create_remote("hub", url=remote_url)
        except Exception as e:
            logging.warning(f"Error setting up hub remote: {str(e)}")

        target_org, target_pkg_name = get_org_repo(remote_url)

        # Get existing open PRs to avoid duplicates
        open_pr_titles = get_open_pr_titles(target_org, target_pkg_name, user_creds)

        pr_branches = {
            name: info
            for name, info in branches.items()
            if not is_open_pr(open_pr_titles, info["org"], info["repo"])
        }

        # Log skipped branches
        for name, info in branches.items():
            if name not in pr_branches.keys():
                logging.info(
                    "PR is already open for {}/{}. Skipping.".format(
                        info["org"], info["repo"]
                    )
                )

        if not pr_branches:
            logging.info("No new branches to push")
            return

        for branch, info in pr_branches.items():
            try:
                target_repo.git.checkout(branch)
                target_repo.git.fetch("hub")

                if push_branches:
                    logging.info(f"Pushing and PRing branch {branch}")

                    try:
                        target_repo.git.push("origin", branch)
                    except GitCommandError as e:
                        if "already up to date" in str(e):
                            logging.info(f"Branch {branch} is already up to date")
                        else:
                            raise ReleaseCarrierError(
                                f"Failed to push branch {branch}: {str(e)}"
                            )

                    make_pr(
                        info["org"],
                        info["repo"],
                        branch,
                        user_creds,
                        pull_request_url,
                        pr_strategy,
                        base=default_branch,
                    )
                else:
                    logging.info(f"Not pushing and PRing branch {branch}")

            except Exception as e:
                logging.error(f"Error processing branch {branch}: {str(e)}")
                continue

    except Exception as e:
        if isinstance(e, ReleaseCarrierError):
            raise
        raise ReleaseCarrierError(f"Unexpected error in open_new_prs: {str(e)}")
