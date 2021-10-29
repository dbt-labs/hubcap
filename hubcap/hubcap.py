import logging
import os
import subprocess
import requests

from pathlib import Path

import setup
import version
import package
import release_carrier

from cmd import *
from records import *

# ==
# == Build global state
# ==

logging.info('preparing script state')
config = setup.build_config()

REMOTE = config['remote']
TMP_DIR = os.environ['GIT_TMP']
PACKAGE_MAINTAINERS = setup.load_package_maintainers()

# pull down hub to assess current state and have ready for future commits
hub_dir_path = clone_repo(REMOTE, TMP_DIR / Path('hub'))

# create a record in memory of what versions are already committed into the hub
HUB_VERSION_INDEX = setup.build_pkg_version_index(hub_dir_path)

# =
# = Determine new package versions
# =

logging.info('cloning package repos')
package.clone_package_repos(PACKAGE_MAINTAINERS, TMP_DIR)

logging.info('collecting the new version tags for packages checked into hub')
update_tasks = package.get_update_tasks(PACKAGE_MAINTAINERS, HUB_VERSION_INDEX, TMP_DIR)

# =
# = Create new specs and commit them to separate branches in hub
# =     (stateful operations from here on)

logging.info('preparing branches for packages with versions to be added')
# this wants to take place inside the git-tmp/hub repo
new_branches = package.commit_version_updates_to_hub(update_tasks, hub_dir_path)

# =
# = push new branches, if there are any
# =

logging.info("Pushing branches: {}".format(list(new_branches.keys())))
if new_branches:
    release_carrier.open_new_prs(Repo(hub_dir_path), REMOTE, new_branches, config['user'])
