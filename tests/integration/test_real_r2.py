"""
Opt-in integration tests that hit a real S3-compatible bucket.

Enable with NIMBUS_INTEGRATION_TESTS=1. Honors the same credentials as the
package itself (R2_ENDPOINT_URL or R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY), and an optional NIMBUS_INTEGRATION_PROJECT to scope
the test namespace inside whatever bucket-type is targeted.
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from nimbus.bucket import NimbusBucketType
from nimbus.config import NimbusCloudConfig
from nimbus.storage import NimbusCloudStorage

ENV_ENABLE = "NIMBUS_INTEGRATION_TESTS"
ENV_BUCKET_TYPE = "NIMBUS_INTEGRATION_BUCKET_TYPE"
ENV_PROJECT = "NIMBUS_INTEGRATION_PROJECT"

DEFAULT_BUCKET_TYPE = NimbusBucketType.CHECKPOINTS
DEFAULT_PROJECT = "integration-tests"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get(ENV_ENABLE, "0") != "1",
        reason=f"set {ENV_ENABLE}=1 to run integration tests",
    ),
]


@pytest.fixture(scope="module")
def storage() -> NimbusCloudStorage:
    config = NimbusCloudConfig.from_env()
    return NimbusCloudStorage(config)


@pytest.fixture
def bucket_type() -> NimbusBucketType:
    raw = os.environ.get(ENV_BUCKET_TYPE, DEFAULT_BUCKET_TYPE.value)
    return NimbusBucketType(raw)


@pytest.fixture
def project() -> str:
    return os.environ.get(ENV_PROJECT, DEFAULT_PROJECT)


@pytest.fixture
def unique_key(
    storage: NimbusCloudStorage, bucket_type: NimbusBucketType, project: str
) -> Iterator[str]:
    """
    Yield a unique key for the test and best-effort delete it afterward.
    """
    key = f"itest/{int(time.time())}-{uuid.uuid4().hex}.bin"
    try:
        yield key
    finally:
        with contextlib.suppress(Exception):
            storage.delete(bucket=bucket_type, project=project, key=key)


def test_upload_exists_list_presign_download_delete_round_trip(
    storage: NimbusCloudStorage,
    bucket_type: NimbusBucketType,
    project: str,
    unique_key: str,
    tmp_path: Path,
) -> None:
    payload = os.urandom(64 * 1024)
    src = tmp_path / "payload.bin"
    src.write_bytes(payload)

    storage.upload_file(
        bucket=bucket_type,
        project=project,
        key=unique_key,
        local_path=src,
        show_progress=False,
    )
    assert storage.exists(bucket=bucket_type, project=project, key=unique_key)

    listed = list(storage.list_keys(bucket=bucket_type, project=project, key_prefix="itest/"))
    assert unique_key in listed

    presigned = storage.presigned_url(
        bucket=bucket_type, project=project, key=unique_key, expires_in=300
    )
    assert presigned.startswith("http")

    dest = tmp_path / "out.bin"
    storage.download_file(
        bucket=bucket_type,
        project=project,
        key=unique_key,
        local_path=dest,
        show_progress=False,
    )
    assert dest.read_bytes() == payload

    storage.delete(bucket=bucket_type, project=project, key=unique_key)
    assert not storage.exists(bucket=bucket_type, project=project, key=unique_key)
