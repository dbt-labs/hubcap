# Release instructions

This application runs on [GitHub Actions](https://github.com/features/actions) and can also be executed in production mode locally. 

**Note**: This application was previously hosted on Heroku. See [GitHub Actions Setup Guide](GITHUB_ACTIONS_SETUP.md) for current deployment instructions.

## Design overview
It is designed to do the following:
1. Use a cron schedule to execute the main `hubcap.py` script at the beginning of every hour
2. The `hubcap.py` script creates a temporary directory to hold cloned git repositories (default is `/target`)
3. `hubcap.py` creates a JSON spec file for each git repo + git tag combo within the `/target/hub.getdbt.com/data/packages/` directory (by default)
4. It opens pull requests against [dbt-labs/hub.getdbt.com](https://github.com/dbt-labs/hub.getdbt.com) for any new versions of dbt packages
    - [Example PR for first-time package](https://github.com/dbt-labs/hub.getdbt.com/pull/1681/files)
    - [Example PR for new version of existing package](https://github.com/dbt-labs/hub.getdbt.com/pull/1683/files)

## Heroku production setup

The commands below assume a production application named `dbt-hubcap`. Replace with `dbt-hubcap-staging` for the staging version of the application.

1. Use the [Heroku Scheduler](https://dashboard.heroku.com/apps/dbt-hubcap/scheduler) to set the following cron schedule:
    - Job: `python3 hubcap.py`
    - Schedule: Every hour at :00
    - Dyno size: Hobby / Standard-1X
1. Configure environment variables: [Settings > Config Vars > Reveal Config Vars](https://dashboard.heroku.com/apps/dbt-hubcap/settings)
    - `CONFIG`: copy format from `config.example.json` and adjust values as needed
    - `GIT_EXEC_PATH`: `/app/.apt/usr/lib/git-core`
1. Setup `git` to be available at app run time. See [these](https://devcenter.heroku.com/articles/heroku-24-stack#changes-to-git) instructions for context.
    ```shell
    heroku buildpacks:add --index 1 heroku-community/apt --app dbt-hubcap
    ```
1. (Re-)deploy the application using the instructions below. See [these](https://dashboard.heroku.com/apps/dbt-hubcap/deploy/heroku-git) instructions for context.


## Heroku production release (automated)

It is possible to configure automatic deploys from GitHub to deploy automatically whenever a specific branch is pushed to: [Deploy > Deployment method > GitHub > Connect to GitHub](https://dashboard.heroku.com/apps/dbt-hubcap/deploy/github).

## Heroku production release (manual)

All of the following steps can be performed locally to initiate a remote deploy on Heroku.

### Install the Heroku CLI
Download and install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-command-line).

If you haven't already, log in to your Heroku account and follow the prompts to create a new SSH public key.

```shell
heroku login
```

### Deploy

To deploy or re-deploy the latest changes:
```shell
git clone git@github.com:dbt-labs/hubcap.git
cd hubcap
git pull origin
git checkout main
heroku git:remote -a dbt-hubcap
git push heroku main:main
```

### Ad hoc executions of the script

For off-schedule ad hoc executions, run the following from the deploy directory above:

```shell
heroku run python3 hubcap.py
```

#### Explanation

`heroku` is the remote that Heroku will use for deploys. `origin` is the source code hosted on GitHub.

Pulling from `origin` will get the latest code in GitHub. Pushing to `heroku` will deploy that latest code to the Heroku app.

You can use the following command to list the tracked repositories:
```shell
git remote -v
```

The result should be something like the following:
```
heroku  https://git.heroku.com/dbt-hubcap.git (fetch)
heroku  https://git.heroku.com/dbt-hubcap.git (push)
origin  git@github.com:dbt-labs/hubcap.git (fetch)
origin  git@github.com:dbt-labs/hubcap.git (push)
```

## GitHub Actions production setup

**Current deployment method**. See [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) for detailed setup instructions.

### Overview
- **Schedule**: Runs automatically every hour at `:00`
- **Environments**: Separate `production` and `test` environments
- **Configuration**: Environment-specific secrets containing JSON configuration
- **Manual execution**: Can be triggered manually via GitHub UI or CLI

### Quick setup
1. Create `production` and `test` environments in repository settings
2. Add `HUBCAP_CONFIG` secret to each environment with appropriate JSON configuration
3. The workflow runs automatically on schedule or can be triggered manually

### Manual execution examples
```bash
# Test environment with dry run (no PRs created)
gh workflow run "Hubcap Scheduler" --field environment=test --field dry_run=true

# Production environment (live)
gh workflow run "Hubcap Scheduler" --field environment=production --field dry_run=false
```

### Monitoring
- View execution logs in repository **Actions** tab
- Each run creates artifacts with logs and generated files
- Failed executions send notifications (if configured)
