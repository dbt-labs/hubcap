import logging
import git_helper
import os
import subprocess
import requests

from pathlib import Path

import setup
import version
import package
import release_carrier

from git_helper import *
from records import *
from records import IndividualPullRequests, ConsolididatedPullRequest


# ==
# == Build global state
# ==

logging.info('preparing script state')
config = setup.build_config()

github_org = config.get("org", "dbt-labs")
github_repo = config.get("repo", "hub.getdbt.com")
push_branches = config.get("push_branches", True)
one_branch_per_repo = config.get("one_branch_per_repo", True)
TOKEN = config['user']['token']
REMOTE = f"https://{TOKEN}@github.com/{github_org}/{github_repo}.git"
PULL_REQUEST_URL = f"https://api.github.com/repos/{github_org}/{github_repo}/pulls"
TMP_DIR = os.environ['GIT_TMP']
GITHUB_USER = config.get('user', {})
GITHUB_USERNAME = GITHUB_USER.get('name', 'dbt-hubcap')
GITHUB_EMAIL = GITHUB_USER.get('email', 'buildbot@fishtownanalytics.com')
TOKEN = GITHUB_USER.get('token')
user_creds = {'name': GITHUB_USERNAME, 'token': TOKEN}
PACKAGE_MAINTAINERS = setup.load_package_maintainers()

if one_branch_per_repo:
    pr_strategy = IndividualPullRequests()
else:
    pr_strategy = ConsolididatedPullRequest()

# pull down hub to assess current state and have ready for future commits
hub_dir_path, repo = clone_repo(REMOTE, TMP_DIR / Path('hub'))

# configure git at the project level
repo.config_writer().set_value("user", "name", GITHUB_USERNAME).release()
repo.config_writer().set_value("user", "email", GITHUB_EMAIL).release()

# create a record in memory of what versions are already committed into the hub
HUB_VERSION_INDEX = setup.build_pkg_version_index(hub_dir_path)

# =
# = Determine new package versions
# =

logging.info('cloning package repos')
package.clone_package_repos(PACKAGE_MAINTAINERS, TMP_DIR, TOKEN)

logging.info('collecting the new version tags for packages checked into hub')
update_tasks = package.get_update_tasks(PACKAGE_MAINTAINERS, HUB_VERSION_INDEX, TMP_DIR)

# =
# = Create new specs and commit them to separate branches in hub
# =     (stateful operations from here on)

logging.info('preparing branches for packages with versions to be added')
# this wants to take place inside the git-tmp/hub repo
new_branches = package.commit_version_updates_to_hub(update_tasks, hub_dir_path, pr_strategy)

# =
# = Add a branch with no commits to confirm that pushing works correctly
# =

branch_name = f'bump-test-{setup.NOW}'

main_dir = Path(TMP_DIR) / 'hub'
os.chdir(main_dir)
completed_subprocess = subprocess.run(['git', 'checkout', '-q', '-b', branch_name])
if completed_subprocess.returncode == 128:
    git_helper.run_cmd(f'git checkout -q {branch_name}')

# Commit an empty file
with open(branch_name, 'w') as fp:
    pass
git_helper.run_cmd('git add -A')
subprocess.run(args=['git', 'commit', '-am', 'Test commit'], capture_output=True)

# Reset back to the default branch
default_branch = 'master'
git_helper.run_cmd(f'git checkout -q {default_branch}')

# Add this branch to the list
new_branches[branch_name] = {'org': 'dbt-labs', 'repo': 'hub.getdbt.com'}

# =
# = push new branches, if there are any
# =

logging.info("Pushing branches: {}".format(list(new_branches.keys())))
if new_branches:
    release_carrier.open_new_prs(hub_dir_path, REMOTE, new_branches, user_creds, push_branches, PULL_REQUEST_URL, pr_strategy)
