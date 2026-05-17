"""
Opt-in integration tests that hit a real S3-compatible bucket.

Enable with NIMBUS_INTEGRATION_TESTS=1. Uses the same credentials as the
package itself (R2_ENDPOINT_URL or R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY). Always writes to NimbusBucketType.TEST under the
INTEGRATION_PROJECT namespace; never touches any other bucket.
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

INTEGRATION_BUCKET_TYPE = NimbusBucketType.TEST
INTEGRATION_PROJECT = "integration-tests"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get(ENV_ENABLE, "0") != "1",
        reason=f"set {ENV_ENABLE}=1 to run integration tests",
    ),
]


@pytest.fixture(scope="module")
def storage() -> NimbusCloudStorage:
    return NimbusCloudStorage(NimbusCloudConfig.from_env())


@pytest.fixture
def unique_key(storage: NimbusCloudStorage) -> Iterator[str]:
    """
    Yield a unique key for the test and best-effort delete it afterward.
    """
    key = f"itest/{int(time.time())}-{uuid.uuid4().hex}.bin"
    try:
        yield key
    finally:
        with contextlib.suppress(Exception):
            storage.delete(bucket=INTEGRATION_BUCKET_TYPE, project=INTEGRATION_PROJECT, key=key)


def test_upload_exists_list_presign_download_delete_round_trip(
    storage: NimbusCloudStorage,
    unique_key: str,
    tmp_path: Path,
) -> None:
    payload = os.urandom(64 * 1024)
    src = tmp_path / "payload.bin"
    src.write_bytes(payload)

    storage.upload_file(
        bucket=INTEGRATION_BUCKET_TYPE,
        project=INTEGRATION_PROJECT,
        key=unique_key,
        local_path=src,
        show_progress=False,
    )
    assert storage.exists(bucket=INTEGRATION_BUCKET_TYPE, project=INTEGRATION_PROJECT, key=unique_key)

    listed = list(
        storage.list_keys(
            bucket=INTEGRATION_BUCKET_TYPE,
            project=INTEGRATION_PROJECT,
            key_prefix="itest/",
        )
    )
    assert unique_key in listed

    presigned = storage.presigned_url(
        bucket=INTEGRATION_BUCKET_TYPE,
        project=INTEGRATION_PROJECT,
        key=unique_key,
        expires_in=300,
    )
    assert presigned.startswith("http")

    dest = tmp_path / "out.bin"
    storage.download_file(
        bucket=INTEGRATION_BUCKET_TYPE,
        project=INTEGRATION_PROJECT,
        key=unique_key,
        local_path=dest,
        show_progress=False,
    )
    assert dest.read_bytes() == payload

    storage.delete(bucket=INTEGRATION_BUCKET_TYPE, project=INTEGRATION_PROJECT, key=unique_key)
    assert not storage.exists(bucket=INTEGRATION_BUCKET_TYPE, project=INTEGRATION_PROJECT, key=unique_key)
