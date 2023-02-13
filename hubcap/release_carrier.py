"""Interface for dispatching updates to packages back to github"""

import json
import requests

from git import Repo
from git.remote import Remote

from hubcap import helper


def make_pr(org, repo, head, user_creds, url, pr_strategy, base="main"):
    """Create POST content which in turns create a hub new-version PR"""
    user = user_creds["name"]
    token = user_creds["token"]
    title = pr_strategy.pull_request_title(org, repo)
    body = "Auto-bumping from new release at https://github.com/{}/{}/releases".format(
        org, repo
    )
    maintainer_can_modify = True
    post_pr(title, head, base, body, maintainer_can_modify, user, token, url)


def post_pr(title, head, base, body, maintainer_can_modify, user, token, url):
    """Create POST content which in turns create a hub new-version PR"""
    body = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
        "maintainer_can_modify": maintainer_can_modify,
    }
    body = json.dumps(body)

    response = requests.post(
        url, data=body, headers={"Content-Type": "application/json"}, auth=(user, token)
    )
    response.raise_for_status()


def get_open_pr_titles(org_name, package_name, user_creds):
    """Prevents opening duplicate PRs for currently open versions"""
    url = f"https://api.github.com/repos/{org_name}/{package_name}/pulls?state=open"

    user = user_creds.get("name", None)
    token = user_creds.get("token", None)
    pr_titles = []

    try:
        response = requests.get(url, auth=(user, token))
        response.raise_for_status()
        pr_titles = [pr["title"] for pr in response.json()]
    except Exception as e:
        helper.logging.error(e)
        helper.logging.info(
            f"Is the {org_name}/{package_name} repository visible to the token's user?"
        )
        helper.logging.info("Does the token have applicable scopes (repo, workflow)?")
        exit(1)

    return pr_titles


def is_open_pr(prs, org_name, pkg_name):
    return any("{}/{}".format(org_name, pkg_name) in pr for pr in prs)


def get_org_repo(remote_url: str) -> str:
    """Parse the organization and repository from a GitHub remote URL."""
    *_, target_org, target_pkg = remote_url.split("/")
    # Strip off "git@github.com:" from the beginning of the organization name
    target_org = target_org.replace("git@github.com:", "")
    # Strip off ".git" from the end of the package name
    target_pkg_name = target_pkg[: -len(".git")]

    return target_org, target_pkg_name


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

    target_repo = Repo(target_repo_path)
    if not Remote(target_repo, "hub").exists():
        target_repo.create_remote("hub", url=remote_url)

    target_org, target_pkg_name = get_org_repo(remote_url)
    # TODO: figure out if this is needed/desired or not
    _ = get_open_pr_titles(target_org, target_pkg_name, user_creds)

    pr_branches = {
        name: info
        for name, info in branches.items()
        if not is_open_pr(name, info["org"], info["repo"])
    }

    for name, info in branches.items():
        if name not in pr_branches.keys():
            helper.logging.info(
                "PR is already open for {}/{}. Skipping.".format(
                    info["org"], info["repo"]
                )
            )

    for branch, info in pr_branches.items():
        target_repo.git.checkout(branch)
        target_repo.git.fetch("hub")

        if push_branches:
            helper.logging.info(f"Pushing and PRing branch {branch}")

            try:
                target_repo.git.push("origin", branch)
            except Exception as e:
                helper.logging.error(e)
                exit(1)

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
            helper.logging.info(f"Not pushing and PRing branch {branch}")
