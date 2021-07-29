
def make_pr(ORG, REPO, head, config):
    url = 'https://api.github.com/repos/dbt-labs/hub.getdbt.com/pulls'
    body = {
        "title": "HubCap: Bump {}/{}".format(ORG, REPO),
        "head": head,
        "base": "master",
        "body": "Auto-bumping from new release at https://github.com/{}/{}/releases".format(ORG, REPO),
        "maintainer_can_modify": True
    }
    body = json.dumps(body)

    user = config['user']['name']
    token = config['user']['token']
    req = requests.post(url, data=body, headers={'Content-Type': 'application/json'}, auth=(user, token))

def get_open_prs(config):
    url = 'https://api.github.com/repos/dbt-labs/hub.getdbt.com/pulls?state=open'

    user = config['user']['name']
    token = config['user']['token']
    req = requests.get(url, auth=(user, token))
    return req.json()

def is_open_pr(prs, ORG, REPO):
    for pr in prs:
        value = '{}/{}'.format(ORG, REPO)
        if value in pr['title']:
            return True

    return False

# push new branches, if there are any
print("Push branches? {} - {}".format(PUSH_BRANCHES, list(new_branches.keys())))
if PUSH_BRANCHES and len(new_branches) > 0:
    hub_dir = os.path.join(TMP_DIR, "ROOT")
    try:
        dbt.clients.system.run_cmd(hub_dir, ['git', 'remote', 'add', 'hub', REMOTE])
    except dbt.exceptions.CommandResultError as e:
        print(e.stderr.decode())

    open_prs = get_open_prs()

    for branch, info in new_branches.items():
        if not info.get('new'):
            print(f"No changes on branch {branch} - Skipping")
            continue
        elif is_open_pr(open_prs, info['org'], info['repo']):
            # don't open a PR if one is already open
            print("PR is already open for {}/{}. Skipping.".format(info['org'], info['repo']))
            continue

        try:
            dbt.clients.system.run_cmd(index_path, ['git', 'checkout', branch])
            try:
                dbt.clients.system.run_cmd(hub_dir, ['git', 'fetch', 'hub'])
            except dbt.exceptions.CommandResultError as e:
                print(e.stderr.decode())

            print("Pushing and PRing for {}/{}".format(info['org'], info['repo']))
            res = dbt.clients.system.run_cmd(hub_dir, ['git', 'push', 'hub', branch])
            print(res[1].decode())
            make_pr(info['org'], info['repo'], branch)
        except Exception as e:
            print(e)

