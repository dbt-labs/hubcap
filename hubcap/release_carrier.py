import json
import requests

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
    response = requests.get(url, auth=(user, token))
    response.raise_for_status()
    return response.json()

def is_open_pr(prs, ORG, REPO):
    for pr in prs:
        value = '{}/{}'.format(ORG, REPO)
        if value in pr['title']:
            return True

    return False
