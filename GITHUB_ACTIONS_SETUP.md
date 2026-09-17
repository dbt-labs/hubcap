# GitHub Actions Setup Guide

This guide explains how to set up hubcap.py to run on GitHub Actions.

## Overview

The GitHub Actions workflow (`hubcap-scheduler.yml`) supports:
- **Scheduled execution**: Runs every hour automatically in production
- **Manual execution**: Can be triggered manually for either test or production
- **Dry-run capability**: Can run without creating PRs for testing
- **Environment isolation**: Separate configurations for test and production

## Setup Steps

### 1. Create GitHub Environments

In your GitHub repository, go to **Settings > Environments** and create two environments:

#### Production Environment
- **Name**: `production`
- **Protection rules**: 
  - ✅ Required reviewers (recommended for production safety)
  - ✅ Wait timer: 0 minutes
- **Environment secrets**: See step 2 below

#### Test Environment  
- **Name**: `test`
- **Protection rules**: None (allows automatic execution)
- **Environment secrets**: See step 2 below

### 2. Configure Environment Secrets

Each environment needs a `HUBCAP_CONFIG` secret with the appropriate configuration.

#### Production Environment Secret
**Secret name**: `HUBCAP_CONFIG`
**Secret value**:
```json
{
  "user": {
    "name": "dbt-hubcap",
    "email": "buildbot@fishtownanalytics.com",
    "token": "ghp_your_production_token_here"
  },
  "org": "dbt-labs",
  "repo": "hub.getdbt.com",
  "push_branches": true,
  "one_branch_per_repo": true
}
```

#### Test Environment Secret
**Secret name**: `HUBCAP_CONFIG`
**Secret value**:
```json
{
  "user": {
    "name": "dbt-hubcap-test",
    "email": "buildbot+test@fishtownanalytics.com",
    "token": "ghp_your_test_token_here"
  },
  "org": "dbt-labs",
  "repo": "hub.getdbt.com-test",
  "push_branches": true,
  "one_branch_per_repo": true
}
```

#### S3 Mirror Configuration

New release tarballs are mirrored to the hub's own bucket, and the resulting URL is
recorded as `downloads.hub` in each version spec. Add an `s3` block to
`HUBCAP_CONFIG` to enable this:

```json
{
  "s3": {
    "bucket": "hub-getdbt-com-packages",
    "region": "us-east-1",
    "key_prefix": "package-hub/dbt-packages",
    "hub_url_base": "https://public.cdn.getdbt.com/package-hub/dbt-packages"
  }
}
```

`key_prefix` and `hub_url_base` default to the values above, so `bucket` is the only
required field. If the `s3` block is omitted entirely, uploads are skipped and specs
are written without a `downloads.hub` entry.

Credentials are obtained via GitHub's OIDC provider rather than static keys: the
workflow assumes the role ARN in the `AWS_ROLE_ARN` repository secret, then boto3
picks up the resulting short-lived credentials from its default credential chain.
This step is skipped on `pull_request` runs, since forked PRs get neither secrets
nor `id-token` permission.

**Secret name**: `AWS_ROLE_ARN`
**Secret value**: `arn:aws:iam::<account-id>:role/<role-name>`

The role's trust policy must allow this repository's GitHub OIDC provider to assume
it, and its permissions policy needs `s3:PutObject` (and ideally `s3:HeadObject`,
used to skip tarballs already mirrored) on `arn:aws:s3:::<bucket>/<key_prefix>/*`.

### 3. GitHub Personal Access Tokens

Create two GitHub Personal Access Tokens:

#### Production Token
- **Scopes**: `repo`, `workflow`
- **Expiration**: Set appropriate expiration
- **Access**: Must have write access to `dbt-labs/hub.getdbt.com`

#### Test Token  
- **Scopes**: `repo`, `workflow`
- **Expiration**: Set appropriate expiration
- **Access**: Must have write access to `dbt-labs/hub.getdbt.com-test`

## Usage

### Automatic Execution (Production)
The workflow runs automatically every hour at `:00` in production mode.

### Manual Execution
You can manually trigger the workflow with different options:

#### Test Environment (Dry Run)
```bash
gh workflow run "Hubcap Scheduler" \
  --field environment=test \
  --field dry_run=true
```

#### Test Environment (Live)
```bash
gh workflow run "Hubcap Scheduler" \
  --field environment=test \
  --field dry_run=false
```

#### Production (Manual)
```bash
gh workflow run "Hubcap Scheduler" \
  --field environment=production \
  --field dry_run=false
```

### Via GitHub Web Interface
1. Go to **Actions > Hubcap Scheduler**
2. Click **Run workflow**
3. Select:
   - **Environment**: `test` or `production`
   - **Dry run**: `true` (no PRs) or `false` (create PRs)
4. Click **Run workflow**

## Monitoring

### Workflow Status
- View execution history in **Actions** tab
- Each run shows environment, duration, and status
- Failed runs will show error details in logs

### Artifacts
Each execution saves:
- `hubcap.log`: Complete execution log
- `target/`: Cloned repositories and generated files
- Retention: 30 days

### Notifications
Configure notifications in repository settings:
- **Settings > Notifications**
- Enable workflow failure notifications
- Set up Slack/email integration if needed

## Troubleshooting

### Common Issues

**Token Permission Errors**
- Verify token has `repo` and `workflow` scopes
- Check token has write access to target repository
- Ensure token hasn't expired

**Configuration Errors**
- Validate JSON syntax in `HUBCAP_CONFIG` secrets
- Check repository names match intended targets
- Verify user email and name are correct

**Execution Failures**
- Check workflow logs for detailed error messages
- Review `hubcap.log` artifact for application-specific errors
- Verify target repository structure and accessibility

### Getting Help
- Check workflow execution logs
- Review artifacts from failed runs
- Test with dry-run mode first
- Use test environment for debugging
