
import collections
import datetime
import hashlib
import json
import os
import subprocess
import requests
import shutil

from pathlib import Path

NOW = int(datetime.datetime.now().timestamp())
NOW_ISO = datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

TMP_DIR = Path.cwd() / Path("git-tmp")

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

os.chdir(TMP_DIR)
subprocess.run(['git', 'clone', REMOTE, 'ROOT'])
os.chdir(git_root_dir)
subprocess.run(['git'], ['checkout'], ['master'])
subprocess.run(['git'], ['pull'], ['origin'], ['master'])

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

def make_spec(org, repo, version, git_path):
    tarball_url = "https://codeload.github.com/{}/{}/tar.gz/{}".format(org, repo, version)
    sha1 = get_sha1(tarball_url)

    project = get_project(git_path)
    packages = [p.to_dict() for p in project.packages.packages]
    package_name = project.project_name

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


def make_index(org_name, repo, existing, tags, git_path):
    description = "dbt models for {}".format(repo)
    assets = {
        "logo": "logos/placeholder.svg".format(repo)
    }

    if isinstance(existing, dict):
        description = existing.get('description', description)
        assets = existing.get('assets', assets)

    import dbt.semver
    version_tags = []
    for tag in tags:
        if tag.startswith('v'):
            tag = tag[1:]

        try:
            version_tag = dbt.semver.VersionSpecifier.from_version_string(tag)
            version_tags.append(version_tag)
        except dbt.exceptions.SemverException as e:
            print("Semver exception for {}. Skipping\n  {}".format(repo, e))

    # find latest tag which is not a prerelease
    latest = version_tags[0]
    for version_tag in version_tags:
        if version_tag > latest and not version_tag.prerelease:
            latest = version_tag

    project = get_project(git_path)
    package_name = project.project_name
    return {
        "name": package_name,
        "namespace": org_name,
        "description": description,
        "latest": latest.to_version_string().replace("=", ""), # LOL
        "assets": assets,
    }

def get_hub_versions(org, repo):
    url = 'https://hub.getdbt.com/api/v1/{}/{}.json'.format(org, repo)
    resp = requests.get(url).json()
    return {r['version'] for r in resp['versions'].values()}

new_branches = {}
for org_name, repos in TRACKED_REPOS.items():
    for repo in repos:
        try:
            clone_url = 'https://github.com/{}/{}.git'.format(org_name, repo)
            git_path = os.path.join(TMP_DIR, repo)

            print("Cloning repo {}".format(clone_url))
            if os.path.exists(git_path):
                shutil.rmtree(path)

            os.chdir(TMP_DIR)
            subprocess.run(['git'], ['clone'], clone_url, repo)

            os.chdir(git_path)
            subprocess.run(['git', 'fetch', '-t'])
            output = subprocess.check_output(['git', 'tag', '--list'])
            tags = set(out.decode('utf-8').strip().split('\n'))

            assert(False)

            project = get_project(git_path)
            package_name = project.project_name

            existing_tags = [i['version'] for i in index[org_name][package_name]]
            print("  Found Tags: {}".format(sorted(tags)))
            print("  Existing Tags: {}".format(sorted(existing_tags)))

            new_tags = set(tags) - set(existing_tags)

            if len(new_tags) == 0:
                print("    No tags to add. Skipping")
                continue

            # check out a new branch for the changes
            if ONE_BRANCH_PER_REPO:
                branch_name = 'bump-{}-{}-{}'.format(org_name, repo, NOW)
            else:
                branch_name = 'bump-{}'.format(NOW)

            index_path = os.path.join(TMP_DIR, "ROOT")
            print("    Checking out branch {} in meta-index".format(branch_name))

            try:
                out, err = dbt.clients.system.run_cmd(index_path, ['git', 'checkout', branch_name])
            except dbt.exceptions.CommandResultError as e:
                dbt.clients.system.run_cmd(index_path, ['git', 'checkout', '-b', branch_name])

            new_branches[branch_name] = {"org": org_name, "repo": package_name}
            index_file_path = os.path.join(index_path, 'data', 'packages', org_name, package_name, 'index.json')

            if os.path.exists(index_file_path):
                existing_index_file_contents = dbt.clients.system.load_file_contents(index_file_path)
                try:
                    existing_index_file = json.loads(existing_index_file_contents)
                except:
                    existing_index_file = []
            else:
                existing_index_file = {}

            new_index_entry = make_index(org_name, repo, existing_index_file, set(tags) | set(existing_tags), git_path)
            repo_dir = os.path.join(index_path, 'data', 'packages', org_name, package_name, 'versions')
            dbt.clients.system.make_directory(repo_dir)
            dbt.clients.system.write_file(index_file_path, json.dumps(new_index_entry, indent=4))

            for i, tag in enumerate(sorted(new_tags)):
                print("    Adding tag: {}".format(tag))

                import dbt.semver
                try:
                    raw_tag = tag
                    if raw_tag.startswith('v'):
                        raw_tag = tag[1:]
                    dbt.semver.VersionSpecifier.from_version_string(raw_tag)
                except dbt.exceptions.SemverException:
                    print("Not semver {}. Skipping".format(raw_tag))
                    continue

                version_path = os.path.join(repo_dir, "{}.json".format(tag))

                print("    Checking out tag {}".format(tag))
                dbt.clients.system.run_cmd(TMP_DIR, ['git', 'checkout', tag])

                package_spec = make_spec(org_name, repo, tag, git_path)
                dbt.clients.system.write_file(version_path, json.dumps(package_spec, indent=4))

                msg = "hubcap: Adding tag {} for {}/{}".format(tag, org_name, repo)
                print("      running `git add`")
                res = dbt.clients.system.run_cmd(repo_dir, ['git', 'add', '-A'])
                if len(res[1]):
                    print("ERROR" + res[1].decode())
                print("      running `git commit`")
                res = dbt.clients.system.run_cmd(repo_dir, ['git', 'commit', '-am', '{}'.format(msg)])
                if len(res[1]):
                    print("ERROR" + res[1].decode())

                new_branches[branch_name]['new'] = True

            # good house keeping
            dbt.clients.system.run_cmd(index_path, ['git', 'checkout', 'master'])
            print()

        except dbt.exceptions.SemverException as e:
            print("Semver exception. Skipping\n  {}".format(e))

        except Exception as e:
            print("Unhandled exception. Skipping\n  {}".format(e))

        except RuntimeError as e:
            print("Unhandled exception. Skipping\n  {}".format(e))

