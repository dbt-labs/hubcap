# Contributing to this repo

## Setup

### Personal access token (PAT)

Follow [these](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) instructions to configure a PAT.

Scopes:
- repo (and all sub-items)
- workflow

Save the token to a secure location. Click the "Configure SSO" button and "Authorize" if applicable.

### Config

```shell
cp config.example.json config.json

# Add your GitHub username and token
$EDITOR config.json

# Export the JSON credentials into an environment variable
export CONFIG=$(<config.json)
```

## Virtual environment

### Install dependencies
Instructions for POSIX bash/zsh (see [here](https://docs.python.org/3/library/venv.html) for syntax for other shells):
```shell
python3 -m venv env
source env/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt -r dev-requirements.txt
source env/bin/activate
```

## Testing locally

```shell
PYTHONPATH=hubcap python -m pytest
```

## Run in test mode

```shell
export ENV=test
./cron.sh
```

### Optional configuration environment variables
```shell
# Default value is the `git-tmp` directory within the current working directory
# This directory will be deleted by default at the end of the run
export GIT_TMP=git-tmp
```

### Optional parameters
Preserve commits/build artifacts within the `$GIT_TMP` directory
```shell
export ENV=test
./cron.sh --no-cleanup
```

## Run in production mode

**WARNING:** Use with caution -- _will_ modify state.
```shell
export ENV=prod
./cron.sh
```
