'''Interface for dispatching updates to packages back to github'''

import json
import requests
import os
import setup

from git import Repo
from git.remote import Remote


def make_pr(ORG, REPO, head, user_creds, url):
    '''Create POST content which in turns create a hub new-version PR'''
    body = {
        "title": "HubCap: Bump {}/{}".format(ORG, REPO),
        "head": head,
        "base": "master",
        "body": "Auto-bumping from new release at https://github.com/{}/{}/releases".format(ORG, REPO),
        "maintainer_can_modify": True
    }
    body = json.dumps(body)

    user = user_creds['name']
    token = user_creds['token']
    response = requests.post(url, data=body, headers={'Content-Type': 'application/json'}, auth=(user, token))
    response.raise_for_status()


def get_open_pr_titles(org_name, package_name, user_creds):
    '''Prevents opening duplicate PRs for currently open versions'''
    url = f'https://api.github.com/repos/{org_name}/{package_name}/pulls?state=open'

    user = user_creds.get('name', None)
    token = user_creds.get('token', None)
    response = requests.get(url, auth=(user, token))
    response.raise_for_status()
    pr_titles = [pr['title'] for pr in response.json()]
    return pr_titles


def is_open_pr(prs, org_name, pkg_name):
    return any('{}/{}'.format(org_name, pkg_name) in pr for pr in prs)


def open_new_prs(target_repo_path, remote_url, branches, user_creds, push_branches, pull_request_url):
    '''Expects: {branch_name: hashmap of branch info} and {user_name, access token}
    will push prs up to a github remote'''

    target_repo = Repo(target_repo_path)
    if not Remote(target_repo, 'hub').exists():
        target_repo.create_remote('hub', url=remote_url)

    *_, target_org, target_pkg = remote_url.split('/')
    # Strip off "git@github.com:" from the beginning of the organization name
    target_org = target_org.replace("git@github.com:", "")
    # Strip off ".git" from the end of the package name
    target_pkg_name = target_pkg[:-len('.git')]
    open_pr_titles = get_open_pr_titles(target_org, target_pkg_name, user_creds)

    pr_branches = { name: info for name, info in branches.items()
                    if not is_open_pr(name, info['org'], info['repo'])}
    for name, info in branches.items():
        if name not in pr_branches.keys():
            setup.logging.info("PR is already open for {}/{}. Skipping.".format(info['org'], info['repo']))

    for branch, info in pr_branches.items():
        target_repo.git.checkout(branch)
        target_repo.git.fetch('hub')

        if push_branches:
            setup.logging.info(f"Pushing and PRing branch {branch}")
            origin = target_repo.git.push('origin', branch)
            make_pr(info['org'], info['repo'], branch, user_creds, pull_request_url)
        else:
            setup.logging.info(f"Not pushing and PRing branch {branch}")
