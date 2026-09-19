"""Tests for the s3_helper module."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from hubcap.exceptions import S3UploadError
from hubcap import s3_helper


S3_CONFIG = {
    "bucket": "hub-getdbt-com-packages",
    "region": "us-east-1",
    "key_prefix": "packages",
    "hub_url_base": "https://hub.getdbt.com/packages",
}


class TestTarballKey:
    """Tests for tarball_key."""

    def test_default_prefix(self):
        key = s3_helper.tarball_key("dbt-labs", "dbt-utils", "1.0.0")
        assert key == "package-hub/dbt-packages/dbt-labs/dbt-utils/tar.gz/1.0.0"

    def test_custom_prefix(self):
        key = s3_helper.tarball_key("dbt-labs", "dbt-utils", "1.0.0", "mirror")
        assert key == "mirror/dbt-labs/dbt-utils/tar.gz/1.0.0"

    def test_prefix_slashes_are_stripped(self):
        """A prefix with stray slashes must not produce a doubled-up key"""
        key = s3_helper.tarball_key("dbt-labs", "dbt-utils", "1.0.0", "/packages/")
        assert key == "packages/dbt-labs/dbt-utils/tar.gz/1.0.0"


class TestHubTarballUrl:
    """Tests for hub_tarball_url."""

    def test_matches_the_hub_serving_path(self):
        url = s3_helper.hub_tarball_url(
            "fishtown-analytics", "dbt-external-tables", "0.4.0"
        )
        assert url == (
            "https://public.cdn.getdbt.com/package-hub/dbt-packages/"
            "fishtown-analytics/dbt-external-tables/tar.gz/0.4.0"
        )

    def test_trailing_slash_on_base_is_stripped(self):
        url = s3_helper.hub_tarball_url(
            "dbt-labs", "dbt-utils", "1.0.0", "https://hub.getdbt.com/packages/"
        )
        assert url == "https://hub.getdbt.com/packages/dbt-labs/dbt-utils/tar.gz/1.0.0"

    def test_key_and_url_share_a_path(self):
        """The bucket is served as-is, so key and URL suffix must agree"""
        key = s3_helper.tarball_key("dbt-labs", "dbt-utils", "1.0.0")
        url = s3_helper.hub_tarball_url("dbt-labs", "dbt-utils", "1.0.0")
        assert url.endswith(key)


class TestBuildClient:
    """Tests for build_client."""

    def test_uses_default_credential_chain(self):
        """With no explicit keys, boto3 resolves credentials itself"""
        with patch("hubcap.s3_helper.boto3.client") as mock_client:
            s3_helper.build_client(S3_CONFIG)

            mock_client.assert_called_once_with("s3", region_name="us-east-1")

    def test_uses_explicit_credentials_when_given(self):
        config = {**S3_CONFIG, "aws_access_key_id": "AK", "aws_secret_access_key": "SK"}

        with patch("hubcap.s3_helper.boto3.client") as mock_client:
            s3_helper.build_client(config)

            mock_client.assert_called_once_with(
                "s3",
                region_name="us-east-1",
                aws_access_key_id="AK",
                aws_secret_access_key="SK",
            )

    def test_includes_session_token_when_given(self):
        config = {
            **S3_CONFIG,
            "aws_access_key_id": "AK",
            "aws_secret_access_key": "SK",
            "aws_session_token": "ST",
        }

        with patch("hubcap.s3_helper.boto3.client") as mock_client:
            s3_helper.build_client(config)

            assert mock_client.call_args.kwargs["aws_session_token"] == "ST"

    def test_partial_credentials_fall_back_to_chain(self):
        """A key id with no secret is unusable, so let boto3 resolve instead"""
        config = {**S3_CONFIG, "aws_access_key_id": "AK"}

        with patch("hubcap.s3_helper.boto3.client") as mock_client:
            s3_helper.build_client(config)

            assert "aws_access_key_id" not in mock_client.call_args.kwargs

    def test_no_region_omits_region_name(self):
        with patch("hubcap.s3_helper.boto3.client") as mock_client:
            s3_helper.build_client({"bucket": "b"})

            mock_client.assert_called_once_with("s3")

    def test_client_failure_raises_s3_upload_error(self):
        with patch("hubcap.s3_helper.boto3.client") as mock_client:
            mock_client.side_effect = Exception("no credentials")

            with pytest.raises(S3UploadError):
                s3_helper.build_client(S3_CONFIG)


class TestObjectExists:
    """Tests for object_exists."""

    def test_true_when_head_succeeds(self):
        client = MagicMock()

        assert s3_helper.object_exists(client, "bucket", "key") is True
        client.head_object.assert_called_once_with(Bucket="bucket", Key="key")

    def test_false_when_object_is_missing(self):
        client = MagicMock()
        client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )

        assert s3_helper.object_exists(client, "bucket", "key") is False

    def test_false_when_check_cannot_be_answered(self):
        """The check is an optimization; an unanswerable check re-uploads"""
        client = MagicMock()
        client.head_object.side_effect = ClientError(
            {"Error": {"Code": "403"}}, "HeadObject"
        )

        assert s3_helper.object_exists(client, "bucket", "key") is False


class TestUploadPackageTarball:
    """Tests for upload_package_tarball."""

    def test_uploads_and_returns_hub_url(self):
        client = MagicMock()
        client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )

        with patch("hubcap.s3_helper.build_client", return_value=client):
            url = s3_helper.upload_package_tarball(
                b"tarball", "dbt-labs", "dbt-utils", "1.0.0", S3_CONFIG
            )

        assert url == "https://hub.getdbt.com/packages/dbt-labs/dbt-utils/tar.gz/1.0.0"
        client.put_object.assert_called_once_with(
            Bucket="hub-getdbt-com-packages",
            Key="packages/dbt-labs/dbt-utils/tar.gz/1.0.0",
            Body=b"tarball",
            ContentType="application/gzip",
        )

    def test_skips_upload_when_already_mirrored(self):
        """Hubcap reruns hourly until a PR merges; re-uploading is wasted work"""
        client = MagicMock()

        with patch("hubcap.s3_helper.build_client", return_value=client):
            url = s3_helper.upload_package_tarball(
                b"tarball", "dbt-labs", "dbt-utils", "1.0.0", S3_CONFIG
            )

        assert url == "https://hub.getdbt.com/packages/dbt-labs/dbt-utils/tar.gz/1.0.0"
        client.put_object.assert_not_called()

    def test_sends_acl_only_when_configured(self):
        client = MagicMock()
        client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )

        with patch("hubcap.s3_helper.build_client", return_value=client):
            s3_helper.upload_package_tarball(
                b"tarball",
                "dbt-labs",
                "dbt-utils",
                "1.0.0",
                {**S3_CONFIG, "acl": "public-read"},
            )

        assert client.put_object.call_args.kwargs["ACL"] == "public-read"

    def test_missing_bucket_raises(self):
        with pytest.raises(S3UploadError, match="bucket"):
            s3_helper.upload_package_tarball(
                b"tarball", "dbt-labs", "dbt-utils", "1.0.0", {"region": "us-east-1"}
            )

    def test_put_failure_raises_s3_upload_error(self):
        client = MagicMock()
        client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadObject"
        )
        client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "PutObject"
        )

        with patch("hubcap.s3_helper.build_client", return_value=client):
            with pytest.raises(S3UploadError):
                s3_helper.upload_package_tarball(
                    b"tarball", "dbt-labs", "dbt-utils", "1.0.0", S3_CONFIG
                )
