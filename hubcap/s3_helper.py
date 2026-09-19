"""Interface for mirroring package release tarballs onto the hub's own storage"""

import logging
from typing import Any, Dict

import boto3

from .exceptions import S3UploadError


DEFAULT_KEY_PREFIX = "package-hub/dbt-packages"
DEFAULT_HUB_URL_BASE = "https://public.cdn.getdbt.com/package-hub/dbt-packages"
TARBALL_CONTENT_TYPE = "application/gzip"


def tarball_key(
    org: str, repo: str, version: str, key_prefix: str = DEFAULT_KEY_PREFIX
) -> str:
    """Key mirrors the public hub path so the bucket can be served as-is"""
    return f"{key_prefix.strip('/')}/{org}/{repo}/tar.gz/{version}"


def hub_tarball_url(
    org: str, repo: str, version: str, hub_url_base: str = DEFAULT_HUB_URL_BASE
) -> str:
    """The URL recorded in a version spec's downloads.hub.tarball"""
    return f"{hub_url_base.rstrip('/')}/{org}/{repo}/tar.gz/{version}"


def build_client(s3_config: Dict[str, Any]):
    """Credentials come from boto3's default chain unless given explicitly in config"""
    try:
        client_kwargs: Dict[str, Any] = {}

        region = s3_config.get("region")
        if region:
            client_kwargs["region_name"] = region

        access_key = s3_config.get("aws_access_key_id")
        secret_key = s3_config.get("aws_secret_access_key")
        if access_key and secret_key:
            client_kwargs["aws_access_key_id"] = access_key
            client_kwargs["aws_secret_access_key"] = secret_key
            session_token = s3_config.get("aws_session_token")
            if session_token:
                client_kwargs["aws_session_token"] = session_token

        return boto3.client("s3", **client_kwargs)
    except Exception as e:
        raise S3UploadError(f"Failed to build S3 client: {str(e)}")


def object_exists(client, bucket: str, key: str) -> bool:
    """Optimization only; an unanswerable check (e.g. no HeadObject permission) re-uploads"""
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as e:
        logging.debug(f"could not confirm s3://{bucket}/{key} already exists: {str(e)}")
        return False


def upload_package_tarball(
    contents: bytes, org: str, repo: str, version: str, s3_config: Dict[str, Any]
) -> str:
    """Mirror a release tarball to the hub bucket and return its public hub URL"""
    bucket = s3_config.get("bucket")
    if not bucket:
        raise S3UploadError("s3 config is missing a 'bucket'")

    key = tarball_key(
        org, repo, version, s3_config.get("key_prefix", DEFAULT_KEY_PREFIX)
    )
    url = hub_tarball_url(
        org, repo, version, s3_config.get("hub_url_base", DEFAULT_HUB_URL_BASE)
    )

    client = build_client(s3_config)

    if object_exists(client, bucket, key):
        logging.info(f"    already mirrored: s3://{bucket}/{key}")
        return url

    put_kwargs: Dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": contents,
        "ContentType": TARBALL_CONTENT_TYPE,
    }
    # Buckets with ACLs disabled reject any ACL, so only send one when configured
    acl = s3_config.get("acl")
    if acl:
        put_kwargs["ACL"] = acl

    try:
        logging.info(f"    uploading to s3://{bucket}/{key}")
        client.put_object(**put_kwargs)
    except Exception as e:
        raise S3UploadError(f"Failed to upload {key} to {bucket}: {str(e)}")

    return url
