
import logging
import subprocess
import requests

from pathlib import Path

from setup import *
from cmd import *

# ==
# == Build global state
# ==

logging.info('preparing script state')
config = build_config()

ONE_BRANCH_PER_REPO = config['one_branch_per_repo']
PUSH_BRANCHES = config['push_branches']
REMOTE = config['remote']
TMP_DIR = os.environ['GIT_TMP']
TRACKED_REPOS = config['tracked_repos']

# ==
# == Pull down the newest version of the hub repo
# ==

hub_dir = TMP_DIR / Path('hub')
logging.info(f'cloning hub site repo to {hub_dir}')
run_cmd(f'git clone --quiet {REMOTE} {hub_dir}')
os.chdir(hub_dir)
run_cmd('git checkout master')
run_cmd('git pull origin master')

index = build_version_index()
new_branches = {}

# ==
# == Cut a branch for each new version of each package
# ==

from version import *
from package import *

logging.info('preparing branches for packages with versions to be added')
for org_name, repos in TRACKED_REPOS.items():
    for repo in repos:
        os.chdir(TMP_DIR)
        current_repo_path = TMP_DIR / Path(repo)

        logging.info(f'cloning package {repo} maintained by {org_name} to {current_repo_path}')
        clone_url = f'https://github.com/{org_name}/{repo}.git'
        run_cmd(f'git clone --quiet {clone_url} {repo}')

        # skip repo if no dbt project yaml or no new tags
        if not has_dbt_project_yml(current_repo_path):
            logging.warning(f'{repo} has no dbt_project.yml. Skipping...')
            continue

        package_name = parse_pkg_name(current_repo_path)
        packages = parse_pkgs(current_repo_path)

        os.chdir(current_repo_path)
        logging.info(f'collecting tags for {package_name}')
        new_tags = get_new_tags(index[org_name][package_name])

        if new_tags:
            logging.info(f'new tags:    {sorted(new_tags)}')
        else:
            logging.warning(f'no new tags for {repo}. Skipping...')
            continue

        # =
        # = Create new specs and commit them to separate branches in hub
        # =

        os.chdir(hub_dir) # will not change until tag loop
        repo_dir = hub_dir / 'data' / 'packages' / org_name / package_name / 'versions'
        Path.mkdir(repo_dir, parents=True, exist_ok=True)

        # in hubcap, on a branch for each package, commit the package version specs for any new tags
        branch_name = cut_version_branch(org_name, repo, ONE_BRANCH_PER_REPO)
        new_branches[branch_name] = {"org": org_name, "repo": package_name}

        # create an updated version of the repo's index.json
        index_file_path = hub_dir / 'data' / 'packages' / org_name / package_name / 'index.json'

        new_index_entry = make_index(
            org_name,
            repo,
            package_name,
            fetch_index_file_contents(index_file_path),
            new_tags | get_existing_tags(index[org_name][package_name]),
            current_repo_path
        )

        with open(index_file_path, 'w') as f:
            logging.info(f'writing index.json to {index_file_path}')
            f.write(str(json.dumps(new_index_entry, indent=4)))

        # create a version spec for each tag
        for tag in new_tags:
            package_spec = make_spec(org_name, repo, package_name, packages, tag, current_repo_path)

            version_path = repo_dir / Path(f'{tag}.json')

            with open(version_path, 'w') as f:
                logging.info(f'writing spec to {version_path}')
                f.write(str(json.dumps(package_spec, indent=4)))

            # checkout tag within current package repo and create JSON spec
            os.chdir(repo_dir)
            msg = f'hubcap: Adding tag {tag} for {org_name}/{repo}'
            logging.info(msg)
            run_cmd('git add -A')
            subprocess.run(args=['git', 'commit', '-am', f'{msg}'], capture_output=True)
            new_branches[branch_name]['new'] = True

        # good house keeping
        os.chdir(hub_dir)
        run_cmd('git checkout master')


# =
# = push new branches, if there are any
# =

from release_carrier import *

logging.info("Push branches? {} - {}".format(PUSH_BRANCHES, list(new_branches.keys())))
if new_branches:
    os.chdir(hub_dir)
    run_cmd(f'git remote add hub {REMOTE}')

    open_prs = get_open_prs(config)

    for branch, info in new_branches.items():
        if not info.get('new'):
            logging.info(f"No changes on branch {branch} - Skipping")
            continue
        elif is_open_pr(open_prs, info['org'], info['repo']):
            logging.info("PR is already open for {}/{}. Skipping.".format(info['org'], info['repo']))
            continue

        os.chdir(hub_dir)
        run_cmd(f'git checkout {branch}')
        run_cmd(f'git fetch hub')

        if PUSH_BRANCHES and (os.environ['ENV'] == 'test' or os.environ['ENV'] == 'prod'):
            logging.info("pushing and PRing for {}/{}".format(info['org'], info['repo']))
            run_cmd(f'git push hub {branch}')
            make_pr(info['org'], info['repo'], branch, config)
