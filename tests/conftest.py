"""
Shared pytest fixtures for the nimbus unit tests.

Every unit test runs inside moto's mock_aws so no real network calls are
made and no credentials are needed.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from moto import mock_aws

from nimbus.bucket import BucketType
from nimbus.config import CloudConfig
from nimbus.storage import CloudStorage

TEST_BUCKET_PREFIX = "test-nimbus"
TEST_REGION = "us-east-1"


@pytest.fixture(autouse=True)
def _clear_nimbus_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Strip every R2_/NIMBUS_ env var so each test starts from a known state.
    """
    for key in list(os.environ):
        if key.startswith(("R2_", "NIMBUS_")):
            monkeypatch.delenv(key, raising=False)


@pytest.fixture
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Dummy AWS credentials so botocore doesn't try to load real ones from
    ~/.aws while moto is active.
    """
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", TEST_REGION)


@pytest.fixture
def mocked_s3(aws_credentials: None) -> Iterator[None]:
    """
    Activate moto's S3 mock for the duration of the test.
    """
    with mock_aws():
        yield


@pytest.fixture
def cloud_config() -> CloudConfig:
    """
    A CloudConfig wired up for moto: us-east-1 region (so create_bucket
    doesn't require a LocationConstraint) and a unique prefix.
    """
    return CloudConfig(
        endpoint_url="https://s3.amazonaws.com",
        access_key_id="testing",
        secret_access_key="testing",
        bucket_prefix=TEST_BUCKET_PREFIX,
        region=TEST_REGION,
    )


@pytest.fixture
def storage(mocked_s3: None, cloud_config: CloudConfig) -> CloudStorage:
    """
    A CloudStorage with all three default buckets pre-created in moto.
    """
    cs = CloudStorage(cloud_config)
    for bucket_type in BucketType:
        cs.client.create_bucket(Bucket=cloud_config.bucket_name(bucket_type))
    return cs
