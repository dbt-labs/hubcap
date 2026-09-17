"""Backfill downloads.hub on existing specs without regenerating release metadata."""

import argparse
from collections import Counter
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from urllib.parse import urlparse

from botocore.exceptions import ClientError
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from hubcap import s3_helper

# Give the CDN a moment to pick up a just-uploaded object before verifying it publicly.
PUBLIC_CHECK_DELAY_SECONDS = 5


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def status_counts(entries):
    return dict(Counter(entry["status"] for entry in entries))


def session():
    client = requests.Session()
    client.mount(
        "https://",
        HTTPAdapter(
            max_retries=Retry(
                total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504]
            )
        ),
    )
    return client


def download(http, url):
    if urlparse(url).scheme != "https":
        raise ValueError("Tarball URL must use HTTPS")
    response = http.get(url, timeout=(15, 120))
    response.raise_for_status()
    return response.content


def _hash_existing(client, bucket, key):
    with client.get_object(Bucket=bucket, Key=key)["Body"] as body:
        return sha1(body.read())


def mirror(client, config, key, contents):
    """Reuse existing bytes; conditional creation prevents overwriting another run."""
    bucket = config["bucket"]
    try:
        digest = _hash_existing(client, bucket, key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("NoSuchKey", "404"):
            raise
    else:
        return digest, "reused"

    kwargs = dict(
        Bucket=bucket,
        Key=key,
        Body=contents,
        ContentType=s3_helper.TARBALL_CONTENT_TYPE,
        IfNoneMatch="*",
    )
    if config.get("acl"):
        kwargs["ACL"] = config["acl"]
    try:
        client.put_object(**kwargs)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "PreconditionFailed":
            raise
        return _hash_existing(client, bucket, key), "reused"
    return sha1(contents), "uploaded"


def backfill(
    hub_dir,
    config,
    report_path,
    *,
    dry_run=True,
    package=None,
    limit=100,
    check_public=True,
):
    root = Path(hub_dir) / "data" / "packages"
    if not root.is_dir():
        raise ValueError(f"Missing package directory: {root}")
    if not config.get("bucket"):
        raise ValueError("Backfill requires s3.bucket")
    # Only the workflow's temporary OIDC credentials may be used.
    if any(k.startswith("aws_") for k in config):
        raise ValueError("Remove static AWS credentials from the S3 configuration")
    client = None if dry_run else s3_helper.build_client(config)
    http = session()
    entries = []
    attempted = 0
    checked = False
    report_path = Path(report_path)

    def save():
        report_path.write_text(
            json.dumps(
                {
                    "dry_run": dry_run,
                    "counts": status_counts(entries),
                    "entries": entries,
                },
                indent=2,
            )
            + "\n"
        )

    save()
    for path in sorted(root.glob("*/*/versions/*.json")):
        package_id = "/".join(path.relative_to(root).parts[:2])
        if package and package_id != package:
            continue
        if limit and attempted >= limit:
            break
        entry = {"spec": str(path.relative_to(hub_dir)), "package": package_id}
        try:
            original = path.read_text()
            spec = json.loads(original)
            downloads = spec["downloads"]
            if downloads.get("hub"):
                entry["status"] = "skipped"
                entries.append(entry)
                continue
            attempted += 1
            entry["source_url"] = downloads["tarball"]
            source = urlparse(spec["_source"]["url"])
            parts = source.path.strip("/").split("/")
            if source.hostname != "github.com" or len(parts) < 2:
                raise ValueError("Cannot identify GitHub repository from _source.url")
            org, repo = parts[:2]
            version = spec["version"]
            key = s3_helper.tarball_key(
                org,
                repo,
                version,
                config.get("key_prefix", s3_helper.DEFAULT_KEY_PREFIX),
            )
            url = s3_helper.hub_tarball_url(
                org,
                repo,
                version,
                config.get("hub_url_base", s3_helper.DEFAULT_HUB_URL_BASE),
            )
            contents = download(http, downloads["tarball"])
            digest = sha1(contents)
            if dry_run:
                entry.update(status="planned", hub_url=url, sha1=digest)
            else:
                digest, action = mirror(client, config, key, contents)
                if check_public and not checked:
                    if action == "uploaded":
                        time.sleep(PUBLIC_CHECK_DELAY_SECONDS)
                    try:
                        if sha1(download(http, url)) != digest:
                            raise ValueError("Public mirror checksum does not match S3")
                    except Exception as exc:
                        entry.update(
                            status="sanity_failed", error=str(exc), hub_url=url
                        )
                        entries.append(entry)
                        save()
                        logging.error("First mirror sanity check failed: %s", exc)
                        break
                    checked = True
                downloads["hub"] = {"tarball": url, "format": "tgz", "sha1": digest}
                path.write_text(
                    json.dumps(spec, indent=4)
                    + ("\n" if original.endswith("\n") else "")
                )
                entry.update(
                    status="updated", hub_url=url, sha1=digest, s3_action=action
                )
        except requests.HTTPError as exc:
            status = exc.response.status_code
            entry.update(
                status="not_found" if status in (404, 410) else "failed",
                http_status=status,
                error=str(exc),
            )
        except Exception as exc:
            entry.update(status="failed", error=str(exc))
        entries.append(entry)
        logging.info("%s: %s", entry["spec"], entry["status"])
        save()
    save()
    http.close()
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hub-dir", type=Path, required=True, help="Existing hub checkout"
    )
    parser.add_argument("--report", type=Path, default=Path("backfill-report.json"))
    parser.add_argument("--package", help="Hub package ID, e.g. dbt-labs/dbt_utils")
    parser.add_argument(
        "--limit", type=int, default=100, help="Candidates per run; 0 = all"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Upload and modify local specs"
    )
    parser.add_argument("--skip-public-check", action="store_true")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("limit must be nonnegative")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = json.loads(os.environ["CONFIG"])
    entries = backfill(
        args.hub_dir,
        config.get("s3", {}),
        args.report,
        dry_run=not args.apply,
        package=args.package,
        limit=args.limit,
        check_public=not args.skip_public_check,
    )
    counts = status_counts(entries)
    logging.info("Backfill summary: %s", counts)
    return int(any(e["status"] in ("failed", "sanity_failed") for e in entries))


if __name__ == "__main__":
    raise SystemExit(main())
