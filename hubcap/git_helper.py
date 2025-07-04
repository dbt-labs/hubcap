"""Interface for invoking CLI executables safely from inside this script"""

import logging
import os
import shutil
import subprocess
from typing import Tuple

from git import cmd
from git import Repo
from git.exc import GitCommandError
from pathlib import Path


class GitOperationError(Exception):
    """Custom exception for git operation failures"""

    pass


def run_cmd(cmd, quiet=False):
    """Dispatching commands to shell from inside Python needs an exit status wrapper"""
    try:
        proc = subprocess.run(
            args=cmd.split(), capture_output=True, timeout=300
        )  # 5 minute timeout

        if proc.returncode:
            stderr_output = proc.stderr.decode("utf-8").rstrip()
            logging.warning(f"Command failed: {cmd}")
            logging.warning(f"Error: {stderr_output}")
            raise GitOperationError(f"Command failed: {cmd}. Error: {stderr_output}")

        output = proc.stdout.decode("utf-8").rstrip()

        if not quiet:
            logging.info(output)

        return output
    except subprocess.TimeoutExpired:
        raise GitOperationError(f"Command timed out: {cmd}")
    except Exception as e:
        raise GitOperationError(f"Unexpected error running command '{cmd}': {str(e)}")


def repo_default_branch(repo):
    """Programmatically obtain a repo's default branch for dynamic repo checkouts"""
    try:
        prev_dir = os.getcwd()
        os.chdir(repo.working_dir)

        remote_info = cmd.Git().remote("show", "origin")
        default_branch_name = remote_info.split("\n")[3].split()[-1]

        os.chdir(prev_dir)
        return default_branch_name
    except (GitCommandError, IndexError) as e:
        logging.error(f"Failed to determine default branch: {str(e)}")
        # Fallback to common default branches
        for branch in ["main", "master"]:
            try:
                repo.git.checkout(branch)
                return branch
            except GitCommandError:
                continue
        raise GitOperationError(
            "Could not determine default branch and no fallback branch found"
        )
    except Exception as e:
        raise GitOperationError(f"Unexpected error getting default branch: {str(e)}")


def clone_repo(remote, path, overwrite=True) -> Tuple[Path, Repo]:
    """Clone down a github repo to a path and a reference to that directory"""

    try:
        if Path(path).is_dir() and overwrite:
            logging.info(f"Removing folder that already exists: {path}")
            shutil.rmtree(path)

        logging.info(f"cloning {remote} to {path}")

        repo = Repo.clone_from(remote, path)

        main_branch = repo_default_branch(repo)
        repo.git.checkout(main_branch)
        logging.info(f"pulling {main_branch} at {path}")
        repo.remotes.origin.pull()
        return path, repo

    except GitCommandError as e:
        if "Repository not found" in str(e):
            raise GitOperationError(f"Repository not found: {remote}")
        elif "Authentication failed" in str(e):
            raise GitOperationError(f"Authentication failed for repository: {remote}")
        elif "Permission denied" in str(e):
            raise GitOperationError(f"Permission denied for repository: {remote}")
        else:
            raise GitOperationError(f"Git command failed for {remote}: {str(e)}")
    except (OSError, IOError) as e:
        raise GitOperationError(f"File system error cloning {remote}: {str(e)}")
    except Exception as e:
        raise GitOperationError(f"Unexpected error cloning {remote}: {str(e)}")


def config_token_authorization(repo, token):
    """
    Handle all 3 git URL styles as authenticated HTTPS URLs using a personal access token (PAT).

    This is the Simplest Bullet™ strategy described here:
    https://coolaj86.com/articles/vanilla-devops-git-credentials-cheatsheet/
    """
    try:
        if not token:
            logging.warning(
                "No GitHub token provided. Some operations may fail due to rate limiting."
            )
            return

        repo.config_writer().set_value(
            f'url "https://api:{token}@github.com/"', "insteadOf", "https://github.com/"
        ).release()
        repo.config_writer().set_value(
            f'url "https://ssh:{token}@github.com/"',
            "insteadOf",
            "ssh://git@github.com/",
        ).release()
        repo.config_writer().set_value(
            f'url "https://git:{token}@github.com/"', "insteadOf", "git@github.com:"
        ).release()
    except Exception as e:
        logging.error(f"Failed to configure token authorization: {str(e)}")
        raise GitOperationError(f"Failed to configure token authorization: {str(e)}")
