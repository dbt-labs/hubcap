import logging

from pathlib import Path

import helper
import package
import release_carrier

from git_helper import config_token_authorization, repo_default_branch, clone_repo
from records import IndividualPullRequests, ConsolididatedPullRequest


# ==
# == Build global state
# ==

logging.info("preparing script state")
config = helper.build_config()

github_org = config.get("org", "dbt-labs")
github_repo = config.get("repo", "hub.getdbt.com")
push_branches = config.get("push_branches", True)
one_branch_per_repo = config.get("one_branch_per_repo", True)
user_config = config.get("user", {})
GITHUB_USERNAME = user_config.get("name", "dbt-hubcap")
GITHUB_EMAIL = user_config.get("email", "buildbot@fishtownanalytics.com")
TOKEN = user_config.get("token")
user_creds = {"name": GITHUB_USERNAME, "token": TOKEN}
REMOTE = f"https://github.com/{github_org}/{github_repo}.git"
PULL_REQUEST_URL = f"https://api.github.com/repos/{github_org}/{github_repo}/pulls"
git_tmp = "target"
TMP_DIR = Path(git_tmp).resolve()
PACKAGE_MAINTAINERS = helper.load_package_maintainers()

if one_branch_per_repo:
    pr_strategy = IndividualPullRequests()
else:
    pr_strategy = ConsolididatedPullRequest()

# pull down hub to assess current state and have ready for future commits
hub_dir_path, repo = clone_repo(REMOTE, TMP_DIR / Path(github_repo))
default_branch = repo_default_branch(repo)

# configure git at the project level
repo.config_writer().set_value("user", "name", GITHUB_USERNAME).release()
repo.config_writer().set_value("user", "email", GITHUB_EMAIL).release()
config_token_authorization(repo, TOKEN)

# create a record in memory of what versions are already committed into the hub
HUB_VERSION_INDEX = helper.build_pkg_version_index(hub_dir_path)

# =
# = Determine new package versions
# =

logging.info("cloning package repos")
package.clone_package_repos(PACKAGE_MAINTAINERS, TMP_DIR)

logging.info("collecting the new version tags for packages checked into hub")
update_tasks = package.get_update_tasks(
    PACKAGE_MAINTAINERS, HUB_VERSION_INDEX, TMP_DIR, github_repo
)

# =
# = Create new specs and commit them to separate branches in hub
# =     (stateful operations from here on)

logging.info("preparing branches for packages with versions to be added")
# branches exist inside the repo located at {TMP_DIR}/{github_repo} (which by default is target/hub.getdbt.com)
new_branches = package.commit_version_updates_to_hub(
    update_tasks, hub_dir_path, pr_strategy, default_branch=default_branch
)

# =
# = push new branches, if there are any
# =

logging.info("Pushing branches: {}".format(list(new_branches.keys())))
if new_branches:
    release_carrier.open_new_prs(
        hub_dir_path,
        REMOTE,
        new_branches,
        user_creds,
        push_branches,
        PULL_REQUEST_URL,
        pr_strategy,
        default_branch=default_branch,
    )
