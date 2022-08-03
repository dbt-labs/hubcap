## Hubcap

Hubcap is the script that generates the pages of the dbt package registry site, [hub.getdbt.com](https://hub.getdbt.com/).

Each hour, `hubcap.py` runs, and checks whether there are new releases for any of the repositories listed in [hub.json](/hub.json). If a new release has been created, or a new package has been added to the list, a Pull Request is opened against the [hub.getdbt.com repository](https://github.com/fishtown-analytics/hub.getdbt.com) to update the the registry site to reflect this. PRs are approved by a member of the Fishtown Analytics team, typically within one business day.

### Caveats and Gotchas
Assorted constraints:
* project must be hosted on GitHub
* your project _must_ have a [dbt_project.yml](https://docs.getdbt.com/reference/dbt_project.yml) with a `name:` tag in the yaml
* if used by your project, a `packages.yml` must live at the root level of your project repository
* only release names that use [semantic versioning](https://semver.org/) will be picked up by hubcap — both `0.1.0` and `v0.1.0` will be picked up, but `first-release` will not.

### Adding your package to hubcap
Currently, only packages hosted on a GitHub repo are supported.

To add your package, open a PR that adds your repository to [hub.json](hub.json). A dbt Labs team member will review your PR and provide a cursory check of your new package against [best practices](package-best-practices.md).