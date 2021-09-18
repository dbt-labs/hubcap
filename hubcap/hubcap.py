import logging
import subprocess
import requests

from pathlib import Path

import setup
import version
import package
import release_carrier

from cmd import *

# ==
# == Build global state
# ==

logging.info('preparing script state')
config = setup.build_config()

ONE_BRANCH_PER_REPO = config['one_branch_per_repo']
REMOTE = config['remote']
TMP_DIR = os.environ['GIT_TMP']
TRACKED_REPOS = setup.load_tracked_repo_records()

# pull down hub to assess current state and have ready for future commits
hub_dir_path = clone_repo(REMOTE, TMP_DIR / Path('hub'))

# create a record in memory of what versions are already committed into the hub
existing_pkg_version_index = setup.build_pkg_version_index(hub_dir_path)

# =
# = Determine new package versions
# =

logging.info('cloning package repos')
package.clone_package_repos(TRACKED_REPOS, TMP_DIR)

logging.info('collecting the new version tags for packages checked into hub')
pkgs_with_updates = package.get_pkgs_with_updates(TRACKED_REPOS, existing_pkg_version_index, TMP_DIR)

# =
# = Create new specs and commit them to separate branches in hub
# =

logging.info('preparing branches for packages with versions to be added')
# this wants to take place inside the git-tmp/hub repo
new_branches = package.commit_version_updates_to_hub(pkgs_with_updates, hub_dir_path, ONE_BRANCH_PER_REPO)

# =
# = push new branches, if there are any
# =

logging.info("Push branches? {}".format(list(new_branches.keys())))
if new_branches:
    release_carrier.open_new_prs(Repo(hub_dir_path), REMOTE, new_branches, config['user'])
