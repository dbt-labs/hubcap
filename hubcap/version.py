"""Interface for package release tags and building package indexes"""

import re
import semver
import logging
from typing import List


class VersionError(Exception):
    """Custom exception for version operation errors"""

    pass


def parse_semver_tag(tag):
    """use regexes to parse the semver tag into groups"""
    try:
        if not isinstance(tag, str):
            return None

        # regex taken from official SEMVER documentation site
        match = re.match(
            r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$",
            tag[1:] if tag.startswith("v") else tag,
        )
        return match
    except Exception as e:
        logging.warning(f"Error parsing semver tag '{tag}': {str(e)}")
        return None


def is_valid_semver_tag(tag):
    """tag is valid according to official semver versioning"""
    try:
        return parse_semver_tag(tag) is not None
    except Exception as e:
        logging.warning(f"Error validating semver tag '{tag}': {str(e)}")
        return False


def is_valid_stable_semver_tag(tag):
    """tag is valid according to official semver versioning but is also stable"""
    try:
        match = parse_semver_tag(tag)
        return match is not None and match.group("prerelease") is None
    except Exception as e:
        logging.warning(f"Error validating stable semver tag '{tag}': {str(e)}")
        return False


def strip_v_from_version(tag):
    """Some release tags are prefixed by a v; removed before releases are added to hub"""
    try:
        if not isinstance(tag, str):
            raise VersionError(f"Invalid tag type: {type(tag)}")

        if tag.startswith("v"):
            return tag[1:]
        else:
            return tag
    except Exception as e:
        raise VersionError(f"Error stripping version prefix from '{tag}': {str(e)}")


def get_existing_tags(version_tags):
    """in: list of version tags
    out: only semver compliant tags"""
    try:
        if not isinstance(version_tags, (list, set)):
            logging.warning(
                f"Invalid version_tags type: {type(version_tags)}, using empty set"
            )
            return set()

        return set(filter(is_valid_semver_tag, version_tags))
    except Exception as e:
        logging.warning(f"Error filtering existing tags: {str(e)}")
        return set()


def get_valid_remote_tags(repo):
    """designed to be run inside a package repo
    Includes semver compliant tags only."""
    try:
        if not repo:
            raise VersionError("Repository object is required")

        repo.git.fetch("--quiet", "--tags")
        all_remote_tags = repo.git.tag("--list").split("\n")

        return set(filter(is_valid_semver_tag, all_remote_tags))
    except Exception as e:
        logging.warning(f"Error getting valid remote tags: {str(e)}")
        return set()


def latest_version(tags: List[str]) -> str:
    """Get the latest final version if one exists and the latest prerelease otherwise."""
    try:
        if not tags:
            raise VersionError("No tags provided")

        # Filter out invalid tags first
        valid_tags = [tag for tag in tags if is_valid_semver_tag(tag)]

        if not valid_tags:
            raise VersionError("No valid semver tags found")

        version_numbers = []
        for tag in valid_tags:
            try:
                version_numbers.append(
                    semver.VersionInfo.parse(strip_v_from_version(tag))
                )
            except Exception as e:
                logging.warning(f"Error parsing version '{tag}': {str(e)}")
                continue

        if not version_numbers:
            raise VersionError("No valid version numbers could be parsed")

        # Prioritize all final versions over any prerelease
        latest_version = max(
            version_numbers, key=lambda v: (v == v.finalize_version(), v)
        )

        return str(latest_version)
    except Exception as e:
        if isinstance(e, VersionError):
            raise
        raise VersionError(f"Unexpected error finding latest version: {str(e)}")
