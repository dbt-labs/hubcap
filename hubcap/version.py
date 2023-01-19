"""Interface for package release tags and building package indexes"""

import re
import semver


def parse_semver_tag(tag):
    """use regexes to parse the semver tag into groups"""
    # regex taken from official SEMVER documentation site
    match = re.match(
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$",
        tag[1:] if tag.startswith("v") else tag,
    )
    return match


def is_valid_semver_tag(tag):
    """tag is valid according to official semver versioning"""
    return parse_semver_tag(tag) is not None


def is_valid_stable_semver_tag(tag):
    """tag is valid according to official semver versioning but is also stable"""
    match = parse_semver_tag(tag)
    return match is not None and match.group("prerelease") is None


def strip_v_from_version(tag):
    """Some release tags are prefixed by a v; removed before releases are added to hub"""
    if tag.startswith("v"):
        return tag[1:]
    else:
        return tag


def get_existing_tags(version_tags):
    """in: list of version tags
    out: only semver compliant tags"""
    return set(filter(is_valid_semver_tag, version_tags))


def get_valid_remote_tags(repo):
    """designed to be run inside a package repo
    Includes semver compliant tags only."""
    repo.git.fetch("--quiet", "--tags")
    all_remote_tags = repo.git.tag("--list").split("\n")

    return set(filter(is_valid_semver_tag, all_remote_tags))


def latest_version(tags: list[str]) -> str:
    """Get the latest final version if one exists and the latest prerelease otherwise."""
    version_numbers = [
        semver.VersionInfo.parse(strip_v_from_version(tag)) for tag in tags
    ]
    # Prioritize all final versions over any prerelease
    latest_version = max(version_numbers, key=lambda v: (v == v.finalize_version(), v))

    return str(latest_version)
