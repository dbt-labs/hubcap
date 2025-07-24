import logging
import sys
from pathlib import Path

from hubcap import helper
from hubcap import package
from hubcap import package_maintainers
from hubcap import release_carrier

from hubcap.git_helper import (
    config_token_authorization,
    repo_default_branch,
    clone_repo,
    GitOperationError,
)
from hubcap.records import IndividualPullRequests, ConsolididatedPullRequest


def main():
    try:
        # ==
        # == Build global state
        # ==

        logging.info("preparing script state")

        try:
            config = helper.build_config()
        except helper.ConfigurationError as e:
            logging.error(f"Configuration error: {str(e)}")
            logging.error(
                "Please ensure CONFIG environment variable is set with valid JSON"
            )
            return 1
        except Exception as e:
            logging.error(f"Unexpected error loading configuration: {str(e)}")
            return 1

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
        PULL_REQUEST_URL = (
            f"https://api.github.com/repos/{github_org}/{github_repo}/pulls"
        )
        git_tmp = "target"
        TMP_DIR = Path(git_tmp).resolve()

        try:
            PACKAGE_MAINTAINERS = package_maintainers.load_package_maintainers()
            if not PACKAGE_MAINTAINERS:
                logging.warning(
                    "No package maintainers found. Check hub.json and exclusions.json files."
                )
        except package_maintainers.PackageMaintainerError as e:
            logging.error(f"Error loading package maintainers: {str(e)}")
            return 1
        except Exception as e:
            logging.error(f"Unexpected error loading package maintainers: {str(e)}")
            return 1

        if one_branch_per_repo:
            pr_strategy = IndividualPullRequests()
        else:
            pr_strategy = ConsolididatedPullRequest()

        # pull down hub to assess current state and have ready for future commits
        try:
            hub_dir_path, repo = clone_repo(REMOTE, TMP_DIR / Path(github_repo))
        except GitOperationError as e:
            logging.error(f"Failed to clone hub repository: {str(e)}")
            logging.error(
                "Please check that the hub repository exists and is accessible"
            )
            return 1
        except Exception as e:
            logging.error(f"Unexpected error cloning hub repository: {str(e)}")
            return 1

        try:
            default_branch = repo_default_branch(repo)
        except GitOperationError as e:
            logging.error(f"Failed to determine default branch: {str(e)}")
            return 1
        except Exception as e:
            logging.error(f"Unexpected error determining default branch: {str(e)}")
            return 1

        # configure git at the project level
        try:
            repo.config_writer().set_value("user", "name", GITHUB_USERNAME).release()
            repo.config_writer().set_value("user", "email", GITHUB_EMAIL).release()
            config_token_authorization(repo, TOKEN)
        except Exception as e:
            logging.error(f"Failed to configure git: {str(e)}")
            return 1

        # create a record in memory of what versions are already committed into the hub
        try:
            HUB_VERSION_INDEX = helper.build_pkg_version_index(hub_dir_path)
        except helper.FileOperationError as e:
            logging.error(f"Error building package version index: {str(e)}")
            logging.error(
                "Please check that the hub repository has the expected structure"
            )
            return 1
        except Exception as e:
            logging.error(f"Unexpected error building package version index: {str(e)}")
            return 1

        # =
        # = Determine new package versions
        # =

        logging.info("cloning package repos")
        failed_repos = package.clone_package_repos(PACKAGE_MAINTAINERS, TMP_DIR)

        if failed_repos and len(failed_repos) == len(
            [
                pkg
                for maintainer in PACKAGE_MAINTAINERS
                for pkg in maintainer.get_packages()
            ]
        ):
            logging.error("All package repositories failed to clone. Exiting.")
            return 1

        logging.info("collecting the new version tags for packages checked into hub")
        try:
            update_tasks = package.get_update_tasks(
                PACKAGE_MAINTAINERS, HUB_VERSION_INDEX, TMP_DIR, github_repo
            )
        except Exception as e:
            logging.error(f"Error getting update tasks: {str(e)}")
            return 1

        if not update_tasks:
            logging.info("No packages have new versions to update")
            return 0

        # =
        # = Create new specs and commit them to separate branches in hub
        # =     (stateful operations from here on)

        logging.info("preparing branches for packages with versions to be added")
        # branches exist inside the repo located at {TMP_DIR}/{github_repo} (which by default is target/hub.getdbt.com)
        try:
            new_branches = package.commit_version_updates_to_hub(
                update_tasks, hub_dir_path, pr_strategy, default_branch=default_branch
            )
        except Exception as e:
            logging.error(f"Error committing version updates: {str(e)}")
            return 1

        # =
        # = push new branches, if there are any
        # =

        logging.info("Pushing branches: {}".format(list(new_branches.keys())))
        if new_branches:
            try:
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
            except Exception as e:
                logging.error(f"Error opening pull requests: {str(e)}")
                return 1

        logging.info("hubcap execution completed successfully")
        return 0

    except KeyboardInterrupt:
        logging.info("hubcap execution interrupted by user")
        return 130
    except Exception as e:
        logging.error(f"Unexpected error in hubcap execution: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
