
import collections
import datetime
import hashlib
import json
import os
import re
import subprocess
import requests
import shutil
import yaml

from pathlib import Path

NOW = int(datetime.datetime.now().timestamp())
NOW_ISO = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

TMP_DIR = Path.cwd() / Path('git-tmp')

config = json.loads(os.environ['CONFIG'])

response = requests.get('https://raw.githubusercontent.com/dbt-labs/hubcap/master/hub.json')
response.raise_for_status()
config['tracked_repos'] = response.json()

TRACKED_REPOS = config['tracked_repos']
ONE_BRANCH_PER_REPO = config['one_branch_per_repo']
PUSH_BRANCHES = config['push_branches']
REMOTE = config['remote']

git_root_dir = TMP_DIR / Path('ROOT')

print("Updating root repo")
Path.mkdir(TMP_DIR, exist_ok=True)
if os.path.exists(git_root_dir):
    shutil.rmtree(git_root_dir)

os.mkdir(git_root_dir)
os.chdir(TMP_DIR)
subprocess.run(['git', 'clone', '-q', REMOTE, 'ROOT'])
os.chdir(git_root_dir)
subprocess.run(['git', 'checkout', '-q', 'master'])
subprocess.run(['git', 'pull', '-q', 'origin', 'master'])

indexed_files = list((git_root_dir / Path('data') / Path('packages')).glob('**/*.json'))
index = collections.defaultdict(lambda : collections.defaultdict(list))
for abs_path in indexed_files:

    filename = os.path.basename(abs_path)
    if filename == 'index.json':
        continue

    pop_1 = os.path.dirname(abs_path)
    pop_2 = os.path.dirname(pop_1)
    pop_3 = os.path.dirname(pop_2)

    repo_name = os.path.basename(pop_2)
    org_name = os.path.basename(pop_3)

    version = filename[:-5]
    info = {"path": abs_path, "version": version}

    if not config.get('refresh', False):
        index[org_name][repo_name].append(info)

def download(url):
    response = requests.get(url)

    file_buf = b""
    for block in response.iter_content(1024*64):
        file_buf += block

    return file_buf

def get_sha1(url):
    print("    downloading: {}".format(url))
    contents = download(url)
    hasher = hashlib.sha1()
    hasher.update(contents)
    digest = hasher.hexdigest()
    print("      SHA1: {}".format(digest))
    return digest

def make_spec(org, repo, package_name, version, git_path):
    tarball_url = "https://codeload.github.com/{}/{}/tar.gz/{}".format(org, repo, version)
    sha1 = get_sha1(tarball_url)

    # note: some packages do not have a packages.yml
    packages = []
    if os.path.exists(git_path / 'packages.yml') and git_path == Path.cwd():
        with open('packages.yml', 'r') as stream:
            packages = yaml.safe_load(stream)['packages']

    return {
        "id": "{}/{}/{}".format(org, package_name, version),
        "name": package_name,
        "version": version,
        "published_at": NOW_ISO,
        "packages": packages,
        "works_with": [],
        "_source": {
            "type": "github",
            "url": "https://github.com/{}/{}/tree/{}/".format(org, repo, version),
            "readme": "https://raw.githubusercontent.com/{}/{}/{}/README.md".format(org, repo, version)
        },
        "downloads": {
            "tarball": tarball_url,
            "format": "tgz",
            "sha1": sha1
        }
    }

def get_proper_version_tags(tags):
    version_tags = []
    for tag in tags:
        if tag.startswith('v'):
            tag = tag[1:]

        # regex taken from official SEMVER documentation site
        match = re.match('^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$', tag)

        if match is not None and match.group('prerelease') is None:
            version_tag = match.group(0)
            version_tags.append(version_tag)

    version_tags.sort(key=lambda s: list(map(int, s.split('.'))))
    return version_tags

def make_index(org_name, repo, package_name, existing, tags, git_path):
    description = "dbt models for {}".format(repo)
    assets = {
        "logo": "logos/placeholder.svg".format(repo)
    }

    if isinstance(existing, dict):
        description = existing.get('description', description)
        assets = existing.get('assets', assets)

    # attempt to grab the latest release version of a project
    sorted_version_tags = get_proper_version_tags(tags)
    if len(sorted_version_tags) < 1:
        latest = ''
    else:
        latest = sorted_version_tags[-1]

    return {
        "name": package_name,
        "namespace": org_name,
        "description": description,
        "latest": latest.replace("=", ""), # LOL
        "assets": assets
    }

def get_hub_versions(org, repo):
    url = 'https://hub.getdbt.com/api/v1/{}/{}.json'.format(org, repo)
    resp = requests.get(url).json()
    return {r['version'] for r in resp['versions'].values()}

new_branches = {}
for org_name, repos in TRACKED_REPOS.items():
    for repo in repos:
        print('> Begin reckoning package {} maintained by {}'.format(repo, org_name))

        clone_url = 'https://github.com/{}/{}.git'.format(org_name, repo)
        git_path = TMP_DIR / Path(repo)

        print('    Cloning repo {}'.format(clone_url))
        if os.path.exists(git_path):
            shutil.rmtree(git_path)

        # operate at head of git-tmp subtree
        os.chdir(TMP_DIR)
        subprocess.run(['git', 'clone', '-q', clone_url, repo])

        # operate within current package repository clone
        os.chdir(git_path)
        subprocess.run(['git', 'fetch', '-q', '-t'])
        output = subprocess.check_output(['git', 'tag', '--list'])
        tags = set(output.decode('utf-8').strip().split('\n'))

        # parse package name
        package_name = ''

        # skip projects that are missing configuration
        if not os.path.exists('dbt_project.yml'):
            continue

        with open('dbt_project.yml', 'r') as stream:
            package_name = yaml.safe_load(stream)['name']

        # assess package releases
        existing_tags = [i['version'] for i in index[org_name][package_name]]
        print("  Found Tags: {}".format(sorted(tags)))
        print("  Existing Tags: {}".format(sorted(existing_tags)))
        new_tags = set(tags) - set(existing_tags)

        if len(new_tags) == 0:
            print('    No tags to add. Skipping')
            continue
        else:
            print("  New Tags: {}".format(sorted(new_tags)))

        # move to the root directory and check out a new branch for the changes
        os.chdir(git_root_dir)
        if ONE_BRANCH_PER_REPO:
            branch_name = 'bump-{}-{}-{}'.format(org_name, repo, NOW)
        else:
            branch_name = 'bump-{}'.format(NOW)

        print("    Checking out branch {} in meta-index".format(branch_name))

        completed_subprocess = subprocess.run(['git', 'checkout', '-q', '-b', branch_name])
        if completed_subprocess.returncode == 128:
            subprocess.run(['git', 'checkout', '-q', branch_name])

        new_branches[branch_name] = {"org": org_name, "repo": package_name}
        index_file_path = git_root_dir / 'data' / 'packages' / org_name / package_name / 'index.json'

        existing_index_file_contents = ''
        if os.path.exists(index_file_path):
            with open(index_file_path, 'rb') as stream:
                existing_index_file_contents = stream.read().decode('utf-8').strip()
            try:
                existing_index_file = json.loads(existing_index_file_contents)
            except:
                existing_index_file = []
        else:
            existing_index_file = {}

        new_index_entry = make_index(org_name, repo, package_name, existing_index_file, set(tags) | set(existing_tags), git_path)

        repo_dir = git_root_dir / 'data' / 'packages' / org_name / package_name / 'versions'
        Path.mkdir(repo_dir, parents=True, exist_ok=True)

        # write index (latest) file spec
        with open(index_file_path, 'w') as f:
            f.write(str(json.dumps(new_index_entry, indent=4)))

        # write file spec for each tag
        for tag in get_proper_version_tags(new_tags):
            print('    Adding tag {}'.format(tag))
            print('    Checking out tag {}'.format(tag))

            version_path = repo_dir / Path('{}.json'.format(tag))

            # checkout tag within current package repo and create JSON spec
            os.chdir(git_path)
            subprocess.run(['git', 'checkout', '-q', tag])
            package_spec = make_spec(org_name, repo, package_name, tag, git_path)

            # return to versions directory in the hub repo to commit changes
            os.chdir(repo_dir)
            with open(version_path, 'w') as f:
                f.write(str(json.dumps(package_spec, indent=4)))

            print('      staging and commiting package spec')
            msg = "hubcap: Adding tag {} for {}/{}".format(tag, org_name, repo)

            subprocess.run(['git', 'add', '-A'])
            subprocess.run(['git', 'commit', '-am', '{}'.format(msg)])

            new_branches[branch_name]['new'] = True

        # good house keeping
        os.chdir(git_root_dir)
        subprocess.run(['git', 'checkout', 'master'])
        print()

from release_carrier import *

# push new branches, if there are any
print("Push branches? {} - {}".format(PUSH_BRANCHES, list(new_branches.keys())))
if PUSH_BRANCHES and len(new_branches) > 0:
    hub_dir = git_root_dir
    os.chdir(git_root_dir)
    subprocess.run(['git', 'remote', 'add', 'hub', REMOTE])

    open_prs = get_open_prs(config)

    for branch, info in new_branches.items():
        if not info.get('new'):
            print(f"No changes on branch {branch} - Skipping")
            continue
        elif is_open_pr(open_prs, info['org'], info['repo']):
            # don't open a PR if one is already open
            print("PR is already open for {}/{}. Skipping.".format(info['org'], info['repo']))
            continue

        os.chdir(hub_dir)
        subprocess.run(['git', 'checkout', branch])
        subprocess.run(['git', 'fetch', 'hub'])

        print("Pushing and PRing for {}/{}".format(info['org'], info['repo']))
        subprocess.run(['git', 'push', 'hub', branch])
        make_pr(info['org'], info['repo'], branch, config)

