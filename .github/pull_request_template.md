## Description 

_Tell us about your new package!_

Link to your package's repository: 

## Checklist
_This checklist is a cut down version of the [best practices](../blob/main/package-best-practices.md) that we have identified as the package hub has grown. Although meeting these checklist items is not a prerequisite to being added to the Hub, we have found that packages which don't conform provide a worse user experience._

### First run experience
- [ ] (Required): The package includes a [licence file detectable by GitHub](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/adding-a-license-to-a-repository), such as the Apache 2.0 or MIT licence.
- [ ] The package includes a README which explains how to get started with the package and customise its behaviour
- [ ] The README indicates which data warehouses/platforms are expected to work with this package

### Customisability
- [ ] The package uses ref or source, instead of hard-coding table references.
#### Packages for data transformation (delete if not relevant):
- [ ] provide a mechanism (such as variables) to customise the location of source tables.
- [ ] do not assume database/schema names in sources.

### Dependencies
#### Dependencies on dbt Core
- [ ] The package has set a supported `require-dbt-version` range in `dbt_project.yml`. Example: A package which depends on functionality added in dbt Core 1.2 should set its `require-dbt-version` property to `[">=1.2.0", "<2.0.0"]`.
#### Dependencies on other packages defined in packages.yml:
- [ ] Dependencies are imported from the dbt Package Hub when available, as opposed to a git installation.
- [ ] Dependencies contain the widest possible range of supported versions, to minimise issues in dependency resolution.
- [ ] In particular, dependencies are not pinned to a patch version unless there is a known incompatibility.
### Interoperability
- [ ] The package does not override dbt Core behaviour in such a way as to impact other dbt resources (models, tests, etc) not provided by the package.
- [ ] The package uses the cross-database macros built into dbt Core where available, such as `{{ dbt.except() }}` and `{{ dbt.type_string() }}`.
- [ ] The package disambiguates its resource names to avoid clashes with nodes that are likely to already exist in a project. For example, packages should not provide a model simply called `users`.

### Versioning
- [ ] (Required): The package's git tags validates against the regex defined in [version.py](/hubcap/version.py)
- [ ] The package's version follows the guidance of Semantic Versioning 2.0.0. (Note in particular the recommendation for production-ready packages to be version 1.0.0 or above)
