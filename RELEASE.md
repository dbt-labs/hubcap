# Release instructions

This application runs on GitHub Actions, but it can also be executed in production mode locally.

## Design overview
It is designed to do the following:
1. Use a cron schedule to execute the main `hubcap.py` script at the beginning of every hour
2. The `hubcap.py` script creates a temporary directory to hold cloned git repositories (default is `/target`)
3. `hubcap.py` creates a JSON spec file for each git repo + git tag combo within the `/target/hub.getdbt.com/data/packages/` directory (by default)
4. It opens pull requests against [dbt-labs/hub.getdbt.com](https://github.com/dbt-labs/hub.getdbt.com) for any new versions of dbt packages
    - [Example PR for first-time package](https://github.com/dbt-labs/hub.getdbt.com/pull/1681/files)
    - [Example PR for new version of existing package](https://github.com/dbt-labs/hub.getdbt.com/pull/1683/files)

## GitHub Actions production setup

See [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md) for detailed setup instructions.

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
