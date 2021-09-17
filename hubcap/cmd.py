
import logging
import os
import subprocess
import sys

from git import cmd
from git import Repo
from pathlib import Path

def run_cmd(cmd, quiet=False):
    proc = subprocess.run(args=cmd.split(), capture_output=True)

    if proc.returncode:
        logging.warning(proc.stderr.decode('utf-8').rstrip())

    output = proc.stdout.decode('utf-8').rstrip()

    if not quiet:
        logging.info(output)

    proc.check_returncode()

    return output


def repo_default_branch(repo):
    prev_dir = os.getcwd()
    os.chdir(repo.working_dir)

    remote_info = cmd.Git().remote('show', 'origin')
    default_branch_name = remote_info.split('\n')[3].split()[-1]

    os.chdir(prev_dir)
    return default_branch_name


def clone_repo(remote, path):
    '''clone down a github repo to a path and a reference to that directory'''
    logging.info(f'cloning {remote} to {path}')
    repo = Repo.clone_from(remote, path)

    main_branch = repo_default_branch(repo)
    repo.git.checkout(main_branch)
    repo.remotes.origin.pull()
    return path
