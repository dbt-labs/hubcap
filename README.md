## Hubcap

Hubcap is the script that generates the pages of the dbt package registry site, [hub.getdbt.com](https://hub.getdbt.com/).

Each hour, `hubcap.py` runs, and checks whether there are new releases for any of the repositories listed in [hub.json](/hub.json). If a new release has been created, or a new package has been added to the list, a Pull Request is opened against the [hub.getdbt.com repository](https://github.com/fishtown-analytics/hub.getdbt.com) to update the the registry site to reflect this. PRs are approved by a member of the Fishtown Analytics team, typically within one business day.

### Adding your package to hubcap
Currently, only packages hosted on a GitHub repo are supported.

To add your package, open a PR that adds your repository to [hub.json](hub.json).

Note that only release names that use [semantic versioning](https://semver.org/) will be picked up by hubcap — both `0.1.0` and `v0.1.0` will be picked up, but `first-release` will not.
