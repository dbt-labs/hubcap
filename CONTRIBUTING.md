# Contributing to this repo

## Virtual environment

### Install dependencies
Instructions for POSIX bash/zsh (see [here](https://docs.python.org/3/library/venv.html) for syntax for other shells):
```shell
python3 -m venv env
source env/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt -r requirements-dev.txt
source env/bin/activate
pre-commit install
```

## Setup

### Personal access token (PAT)

Follow [these](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) instructions to configure a PAT in GitHub.

Scopes:
- repo (and all sub-items)
- workflow

Save the token to a secure location. Click the "Configure SSO" button and "Authorize" if applicable.

### Config

```shell
cp config.example.json config.json

# Add the relevant GitHub username, email address and token
$EDITOR config.json

# Export the JSON credentials into an environment variable
export CONFIG=$(<config.json)
```

## Run in test mode

### Local testing
- Set `"repo": "hub.getdbt.com-test"` within `config.json` (or specify some other non-production repository).
- Optional: set `"push_branches": false` within `config.json`.

Run:
```shell
python3 hubcap.py
```

### GitHub Actions testing
You can also test using the GitHub Actions workflow:
```shell
# Test with dry run (no PRs created)
gh workflow run "Hubcap Scheduler" --field environment=test --field dry_run=true

# Test with live PR creation to test repo
gh workflow run "Hubcap Scheduler" --field environment=test --field dry_run=false
```

See [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) for setup instructions.

## Run in production mode

**WARNING:** Use with caution -- _will_ modify state.
- Set `"repo": "hub.getdbt.com"` within `config.json` (since [hub.getdbt.com](https://github.com/dbt-labs/hub.getdbt.com) is the production repository).
- Set `"push_branches": true` within `config.json`.

Run:
```shell
python3 hubcap.py
```

## Testing locally

```shell
python -m pytest
```

Or just:
```shell
tox
```

## GitHub Actions (GHA) locally

Download and install [`act`](https://github.com/nektos/act) then:

```shell
act
```

For Apple M1 Mac users, might need to do this:
```shell
act --container-architecture linux/amd64
```

## Generate requirements.txt

Put any first degree dependencies within `requirements.in`, then run:

```shell
pip-compile
```

It will generate a new version of `requirements.txt` with each transitive dependency pinned to a specific version.
