import hashlib
import io
import json
import sys
from unittest.mock import Mock

from botocore.exceptions import ClientError
import pytest
import requests

from hubcap import backfill


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root = tmp_path / "data/packages/acme/dbt_name/versions"
    root.mkdir(parents=True)
    spec = {
        "version": "1.0.0",
        "name": "dbt_name",
        "_source": {"url": "https://github.com/acme/repository/tree/1.0.0/"},
        "downloads": {
            "tarball": "https://example.com/source",
            "sha1": "old",
            "format": "tgz",
        },
        "packages": [{"package": "other/dependency", "version": "1"}],
        "fusion_compatibility": {"preserve": True},
    }
    path = root / "1.0.0.json"
    path.write_text(json.dumps(spec, indent=4))
    client = Mock()
    client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}}, "GetObject"
    )
    monkeypatch.setattr(backfill.s3_helper, "build_client", Mock(return_value=client))
    http = Mock()
    http.get.return_value.content = b"fresh bytes"
    monkeypatch.setattr(backfill, "session", lambda: http)
    monkeypatch.setattr(backfill.time, "sleep", Mock())
    return tmp_path, path, spec, client, http


def execute(setup, **kwargs):
    root, path, spec, client, http = setup
    return backfill.backfill(root, {"bucket": "bucket"}, root / "report.json", **kwargs)


def test_fresh_checksum_and_metadata_preserved(setup):
    root, path, spec, client, http = setup
    entries = execute(setup, dry_run=False)
    updated = json.loads(path.read_text())
    hub = updated["downloads"].pop("hub")
    assert updated == spec
    assert hub["sha1"] == hashlib.sha1(b"fresh bytes").hexdigest()
    assert "/acme/repository/tar.gz/1.0.0" in hub["tarball"]
    assert entries[0]["status"] == "updated"
    assert client.put_object.call_args.kwargs["IfNoneMatch"] == "*"
    assert http.get.call_count == 2


def test_dry_run_does_not_write(setup):
    root, path, spec, client, http = setup
    original = path.read_bytes()
    assert execute(setup)[0]["status"] == "planned"
    assert path.read_bytes() == original
    client.get_object.assert_not_called()
    client.put_object.assert_not_called()


def test_reuse_checksum_from_stored_bytes(setup):
    root, path, spec, client, http = setup
    client.get_object.side_effect = None
    client.get_object.return_value = {"Body": io.BytesIO(b"older mirror")}
    execute(setup, dry_run=False, check_public=False)
    assert (
        json.loads(path.read_text())["downloads"]["hub"]["sha1"]
        == hashlib.sha1(b"older mirror").hexdigest()
    )
    client.put_object.assert_not_called()


def test_public_check_waits_before_verifying_fresh_upload(setup):
    root, path, spec, client, http = setup
    execute(setup, dry_run=False)
    backfill.time.sleep.assert_called_once_with(backfill.PUBLIC_CHECK_DELAY_SECONDS)


def test_public_check_skips_wait_when_mirror_already_existed(setup):
    root, path, spec, client, http = setup
    client.get_object.side_effect = None
    client.get_object.return_value = {"Body": io.BytesIO(b"fresh bytes")}
    execute(setup, dry_run=False)
    backfill.time.sleep.assert_not_called()


def test_missing_source_logged_and_next_version_processed(setup):
    root, path, spec, client, http = setup
    second = path.with_name("2.0.0.json")
    second.write_text(json.dumps({**spec, "version": "2.0.0"}))
    response = Mock(status_code=404)
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    http.get.side_effect = [response, Mock(content=b"second")]
    entries = execute(setup, dry_run=False, check_public=False)
    assert [e["status"] for e in entries] == ["not_found", "updated"]
    assert entries[0]["http_status"] == 404
    assert entries[0]["source_url"] == spec["downloads"]["tarball"]
    assert json.loads(path.read_text()) == spec


def test_s3_permission_error_never_overwrites_or_patches(setup):
    root, path, spec, client, http = setup
    client.get_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied"}}, "GetObject"
    )
    assert execute(setup, dry_run=False)[0]["status"] == "failed"
    client.put_object.assert_not_called()
    assert json.loads(path.read_text()) == spec


def test_public_check_failure_stops_batch(setup):
    root, path, spec, client, http = setup
    path.with_name("2.0.0.json").write_text(json.dumps(spec))
    http.get.side_effect = [Mock(content=b"fresh"), Mock(content=b"wrong")]
    assert execute(setup, dry_run=False)[0]["status"] == "sanity_failed"
    assert json.loads(path.read_text()) == spec
    assert client.put_object.call_count == 1


def test_public_check_once_and_completed_specs_skipped(setup):
    root, path, spec, client, http = setup
    path.with_name("2.0.0.json").write_text(json.dumps({**spec, "version": "2.0.0"}))
    execute(setup, dry_run=False)
    assert http.get.call_count == 3
    http.get.reset_mock()
    assert all(e["status"] == "skipped" for e in execute(setup, dry_run=False))
    http.get.assert_not_called()


def test_filter_and_limit(setup):
    root, path, spec, client, http = setup
    path.with_name("2.0.0.json").write_text(json.dumps(spec))
    assert execute(setup, package="someone/else") == []
    assert len(execute(setup, package="acme/dbt_name", limit=1)) == 1


def test_conditional_upload_race_reuses_winner():
    client = Mock()
    client.get_object.side_effect = [
        ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject"),
        {"Body": io.BytesIO(b"winner")},
    ]
    client.put_object.side_effect = ClientError(
        {"Error": {"Code": "PreconditionFailed"}}, "PutObject"
    )
    assert backfill.mirror(client, {"bucket": "bucket"}, "key", b"loser") == (
        hashlib.sha1(b"winner").hexdigest(),
        "reused",
    )


@pytest.mark.parametrize("apply", [False, True])
def test_local_cli_needs_no_github_credentials(tmp_path, monkeypatch, apply):
    monkeypatch.setenv("CONFIG", json.dumps({"s3": {"bucket": "bucket"}}))
    argv = ["backfill", "--hub-dir", str(tmp_path)]
    if apply:
        argv.append("--apply")
    monkeypatch.setattr(sys, "argv", argv)
    process = Mock(return_value=[{"status": "updated"}, {"status": "failed"}])
    monkeypatch.setattr(backfill, "backfill", process)
    assert backfill.main() == 1
    assert process.call_args.kwargs["dry_run"] is not apply
