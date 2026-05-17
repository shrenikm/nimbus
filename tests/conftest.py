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

from nimbus.bucket import NimbusBucketType
from nimbus.config import NimbusCloudConfig
from nimbus.storage import NimbusCloudStorage

TEST_REGION = "us-east-1"


@pytest.fixture(autouse=True)
def _isolate_nimbus_env(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Strip every R2_/NIMBUS_ env var and disable .env loading so each unit
    test starts from a known, hermetic state — even if the developer has a
    real .env file in the project root.

    Skipped for tests marked `integration`, which intentionally need the
    real environment and .env to talk to a live S3-compatible bucket.
    """
    if request.node.get_closest_marker("integration") is not None:
        return
    for key in list(os.environ):
        if key.startswith(("R2_", "NIMBUS_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("nimbus.config.load_dotenv", lambda *a, **kw: False)


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
def cloud_config() -> NimbusCloudConfig:
    """
    A NimbusCloudConfig wired up for moto: us-east-1 region so create_bucket
    doesn't require a LocationConstraint.
    """
    return NimbusCloudConfig(
        endpoint_url="https://s3.amazonaws.com",
        access_key_id="testing",
        secret_access_key="testing",
        region=TEST_REGION,
    )


@pytest.fixture
def storage(mocked_s3: None, cloud_config: NimbusCloudConfig) -> NimbusCloudStorage:
    """
    A NimbusCloudStorage with all three default buckets pre-created in moto.
    """
    cs = NimbusCloudStorage(cloud_config)
    for bucket_type in NimbusBucketType:
        cs.client.create_bucket(Bucket=cloud_config.bucket_name(bucket_type))
    return cs
