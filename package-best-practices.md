# Best practices when submitting a package for public use

Packages are a key part of the dbt experience. Practitioners and vendors alike can [contribute to the knowledge loop](https://github.com/dbt-labs/corp/blob/main/values.md#we-contribute-to-the-knowledge-loop) by enabling compelling, batteries-included use cases.

There are hundreds of packages on the dbt Package Hub already, and over time we have identified a handful of common mistakes that new package authors make as they take a self-contained package and prepare it for publication. We have listed these below to help you and your users get the best experience.

Although the dbt Labs team completes a cursory review of new packages before adding them to the Package Hub, ultimately you are responsible for your package's performance.

To avoid ambiguity, the bullets below are pretty formal, but we are a friendly bunch! If you need help preparing a package for deployment to the dbt Package Hub, reach out in [#package-ecosystem](https://getdbt.slack.com/archives/CU4MRJ7QB/) in the [dbt Community Slack](https://getdbt.com/community).

---

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED",  "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

### First run experience
- Packages SHOULD contain a README file which explains how to get started with the package and customise its behaviour.
- The documentation SHOULD indicate which data warehouses are expected to work with this package.

### Customisability 
- Packages MUST NOT hard-code table references, and MUST use `ref` or `source` instead.
- Packages MAY provide a mechanism (such as variables) to enable/disable certain subsets of functionality.
- Packages for data transformation:
    - SHOULD provide a mechanism (such as variables) to customise the location of source tables.
    - SHOULD NOT assume database/schema names in sources. 
    - MAY assume table names, particularly if the package was built to support tables created by a known tool.

### Dependencies
#### Dependencies on dbt Core
- Packages requiring a minimum version of `dbt-core` MUST declare it in the `require-dbt-version` property of `dbt_project.yml`.
- Packages requiring a minimum version of `dbt-core` SHOULD allow all subsequent minor and patch releases of that major version. 
    - For example, a package which depends on functionality added in dbt Core 1.2 SHOULD set its `require-dbt-version` property to `[">=1.2.0", "<2.0.0"]`.
#### Dependencies on other packages defined in `packages.yml`:
- Packages SHOULD import their dependencies from the dbt Package Hub when available, as opposed to a `git` installation.
- Packages SHOULD specify the widest possible range of supported versions, to minimise issues in dependency resolution. 
    - In particular, packages SHOULD NOT pin to a patch version of their imported package unless they are aware of an incompatibility.
### Interoperability
- Packages MUST NOT override dbt Core behaviour in such a way as to impact other dbt resources (models, tests, etc) not provided by the package.
- Packages SHOULD use the cross-database macros built into dbt Core where available, such as `{{ except() }}` and `{{ type_string() }}`.
- Packages SHOULD disambiguate their resource names to avoid clashes with nodes that are likely to already exist in a project. 
    - For example, packages SHOULD NOT provide a model simply called `users`.

### Releases and updates
- Packages' git tags MUST validate against the regex defined in [version.py](/hubcap/version.py).
- Packages SHOULD follow the guidance of [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).