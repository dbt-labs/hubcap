
import logging
import subprocess
import requests

from pathlib import Path

import setup
import version
import package

from cmd import *

# ==
# == Build global state
# ==

logging.info('preparing script state')
config = setup.build_config()

ONE_BRANCH_PER_REPO = config['one_branch_per_repo']
PUSH_BRANCHES = config['push_branches']
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

from release_carrier import *

logging.info("Push branches? {} - {}".format(PUSH_BRANCHES, list(new_branches.keys())))
if new_branches:
    os.chdir(hub_dir_path)
    run_cmd(f'git remote add hub {REMOTE}')

    open_prs = get_open_prs(config)

    for branch, info in new_branches.items():
        if not info.get('new'):
            logging.info(f"No changes on branch {branch} - Skipping")
            continue
        elif is_open_pr(open_prs, info['org'], info['repo']):
            logging.info("PR is already open for {}/{}. Skipping.".format(info['org'], info['repo']))
            continue

        os.chdir(hub_dir_path)
        run_cmd(f'git checkout {branch}')
        run_cmd(f'git fetch hub')

        if PUSH_BRANCHES and os.environ['ENV'] == 'prod':
            logging.info("pushing and PRing for {}/{}".format(info['org'], info['repo']))
            run_cmd(f'git push hub {branch}')
            make_pr(info['org'], info['repo'], branch, config)
