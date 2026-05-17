from __future__ import annotations

import os
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from nimbus.bucket import NimbusBucketType
from nimbus.exceptions import (
    NimbusObjectNotFoundError,
    NimbusStorageError,
    NimbusValidationError,
)
from nimbus.storage import (
    DEFAULT_MULTIPART_CHUNKSIZE,
    DEFAULT_MULTIPART_THRESHOLD,
    NimbusCloudStorage,
    default_transfer_config,
)

PROJECT = "my-project"


class TestTransferDefaults:
    def test_defaults_match_spec(self) -> None:
        transfer_config = default_transfer_config()
        assert transfer_config.multipart_threshold == DEFAULT_MULTIPART_THRESHOLD
        assert transfer_config.multipart_chunksize == DEFAULT_MULTIPART_CHUNKSIZE
        assert transfer_config.max_request_concurrency == 10
        assert transfer_config.use_threads is True
        assert DEFAULT_MULTIPART_THRESHOLD == 50 * 1024 * 1024
        assert DEFAULT_MULTIPART_CHUNKSIZE == 50 * 1024 * 1024


class TestUploadDownload:
    def test_upload_and_download_round_trip(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        payload = b"hello-world"
        src = tmp_path / "src.bin"
        src.write_bytes(payload)

        storage.upload_file(
            bucket=NimbusBucketType.CHECKPOINTS,
            project=PROJECT,
            key="run-1/best.pth",
            local_path=src,
            show_progress=False,
        )

        dest = tmp_path / "out" / "best.pth"
        downloaded = storage.download_file(
            bucket=NimbusBucketType.CHECKPOINTS,
            project=PROJECT,
            key="run-1/best.pth",
            local_path=dest,
            show_progress=False,
        )
        assert downloaded == dest
        assert dest.read_bytes() == payload

    def test_upload_returns_full_key(self, storage: NimbusCloudStorage, tmp_path: Path) -> None:
        src = tmp_path / "a.bin"
        src.write_bytes(b"x")
        object_key = storage.upload_file(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key="folder/a.bin",
            local_path=src,
            show_progress=False,
        )
        assert object_key == f"{PROJECT}/folder/a.bin"

    def test_upload_rejects_nonexistent_local_file(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        with pytest.raises(NimbusValidationError):
            storage.upload_file(
                bucket=NimbusBucketType.DATASETS,
                project=PROJECT,
                key="a.bin",
                local_path=tmp_path / "does-not-exist.bin",
                show_progress=False,
            )

    def test_upload_rejects_directory(self, storage: NimbusCloudStorage, tmp_path: Path) -> None:
        with pytest.raises(NimbusValidationError):
            storage.upload_file(
                bucket=NimbusBucketType.DATASETS,
                project=PROJECT,
                key="a.bin",
                local_path=tmp_path,
                show_progress=False,
            )

    def test_download_missing_object_raises_not_found(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        with pytest.raises(NimbusObjectNotFoundError):
            storage.download_file(
                bucket=NimbusBucketType.CHECKPOINTS,
                project=PROJECT,
                key="missing/object.bin",
                local_path=tmp_path / "out.bin",
                show_progress=False,
            )

    def test_upload_to_missing_bucket_raises_storage_error(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        src = tmp_path / "x"
        src.write_bytes(b"y")
        storage.client.delete_bucket(
            Bucket=storage.config.bucket_name(NimbusBucketType.CHECKPOINTS)
        )
        with pytest.raises(NimbusStorageError):
            storage.upload_file(
                bucket=NimbusBucketType.CHECKPOINTS,
                project=PROJECT,
                key="run/a.bin",
                local_path=src,
                show_progress=False,
            )


class TestMultipartUpload:
    def test_multipart_upload_round_trip(self, storage: NimbusCloudStorage, tmp_path: Path) -> None:
        large_size = DEFAULT_MULTIPART_THRESHOLD + 2 * 1024 * 1024
        src = tmp_path / "large.bin"
        with src.open("wb") as fh:
            written = 0
            chunk = os.urandom(1024 * 1024)
            while written < large_size:
                fh.write(chunk)
                written += len(chunk)

        storage.upload_file(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key="big/file.bin",
            local_path=src,
            show_progress=False,
        )

        dest = tmp_path / "downloaded.bin"
        storage.download_file(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key="big/file.bin",
            local_path=dest,
            show_progress=False,
        )
        assert dest.stat().st_size == src.stat().st_size


class TestUploadDir:
    def test_uploads_all_files_recursively(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        root = tmp_path / "dataset"
        (root / "a").mkdir(parents=True)
        (root / "a" / "b").mkdir()
        (root / "a" / "one.txt").write_text("1")
        (root / "a" / "b" / "two.txt").write_text("2")
        (root / "top.txt").write_text("0")

        uploaded = storage.upload_dir(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key_prefix="release-v1/",
            local_dir=root,
            show_progress=False,
        )

        assert sorted(uploaded) == [
            f"{PROJECT}/release-v1/a/b/two.txt",
            f"{PROJECT}/release-v1/a/one.txt",
            f"{PROJECT}/release-v1/top.txt",
        ]

    def test_empty_prefix_uploads_directly_under_project(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        root = tmp_path / "dataset"
        root.mkdir()
        (root / "file.bin").write_bytes(b"x")
        uploaded = storage.upload_dir(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key_prefix="",
            local_dir=root,
            show_progress=False,
        )
        assert uploaded == [f"{PROJECT}/file.bin"]

    def test_prefix_without_trailing_slash_is_padded(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        root = tmp_path / "dataset"
        root.mkdir()
        (root / "x.bin").write_bytes(b"x")
        uploaded = storage.upload_dir(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key_prefix="release-v1",
            local_dir=root,
            show_progress=False,
        )
        assert uploaded == [f"{PROJECT}/release-v1/x.bin"]

    def test_missing_directory_raises(self, storage: NimbusCloudStorage, tmp_path: Path) -> None:
        with pytest.raises(NimbusValidationError):
            storage.upload_dir(
                bucket=NimbusBucketType.DATASETS,
                project=PROJECT,
                key_prefix="",
                local_dir=tmp_path / "missing",
                show_progress=False,
            )


class TestListExistsDelete:
    def _upload(
        self, storage: NimbusCloudStorage, tmp_path: Path, *, key: str, data: bytes = b"x"
    ) -> None:
        path = tmp_path / "u.bin"
        path.write_bytes(data)
        storage.upload_file(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key=key,
            local_path=path,
            show_progress=False,
        )

    def test_list_keys_yields_keys_with_project_stripped(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        self._upload(storage, tmp_path, key="a.bin")
        self._upload(storage, tmp_path, key="folder/b.bin")
        keys = sorted(storage.list_keys(bucket=NimbusBucketType.DATASETS, project=PROJECT))
        assert keys == ["a.bin", "folder/b.bin"]

    def test_list_keys_pagination(self, storage: NimbusCloudStorage, tmp_path: Path) -> None:
        for index in range(25):
            self._upload(storage, tmp_path, key=f"many/item-{index:03d}.bin")

        bucket_name = storage.config.bucket_name(NimbusBucketType.DATASETS)
        original_paginate = storage.client.get_paginator("list_objects_v2").paginate

        def small_pages(*args: object, **kwargs: object):
            kwargs = {**kwargs, "PaginationConfig": {"PageSize": 5}}
            return original_paginate(*args, **kwargs)

        paginator = storage.client.get_paginator("list_objects_v2")
        paginator.paginate = small_pages  # type: ignore[method-assign]

        def mocked_get_paginator(_name: str):
            return paginator

        storage.client.get_paginator = mocked_get_paginator  # type: ignore[method-assign]

        keys = sorted(
            storage.list_keys(bucket=NimbusBucketType.DATASETS, project=PROJECT, key_prefix="many/")
        )
        assert len(keys) == 25
        assert keys[0] == "many/item-000.bin"
        assert bucket_name  # silence unused warning

    def test_list_keys_with_prefix(self, storage: NimbusCloudStorage, tmp_path: Path) -> None:
        self._upload(storage, tmp_path, key="folder/a.bin")
        self._upload(storage, tmp_path, key="other/b.bin")
        keys = sorted(
            storage.list_keys(
                bucket=NimbusBucketType.DATASETS, project=PROJECT, key_prefix="folder/"
            )
        )
        assert keys == ["folder/a.bin"]

    def test_exists_true_and_false(self, storage: NimbusCloudStorage, tmp_path: Path) -> None:
        self._upload(storage, tmp_path, key="present.bin")
        assert storage.exists(bucket=NimbusBucketType.DATASETS, project=PROJECT, key="present.bin")
        assert not storage.exists(
            bucket=NimbusBucketType.DATASETS, project=PROJECT, key="absent.bin"
        )

    def test_delete_removes_object(self, storage: NimbusCloudStorage, tmp_path: Path) -> None:
        self._upload(storage, tmp_path, key="doomed.bin")
        storage.delete(bucket=NimbusBucketType.DATASETS, project=PROJECT, key="doomed.bin")
        assert not storage.exists(
            bucket=NimbusBucketType.DATASETS, project=PROJECT, key="doomed.bin"
        )

    def test_delete_missing_is_silent(self, storage: NimbusCloudStorage) -> None:
        storage.delete(bucket=NimbusBucketType.DATASETS, project=PROJECT, key="never-existed.bin")


class TestPresignedUrl:
    def test_returns_url_with_bucket_and_key(
        self, storage: NimbusCloudStorage, tmp_path: Path
    ) -> None:
        src = tmp_path / "presign.bin"
        src.write_bytes(b"abc")
        storage.upload_file(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key="folder/object.bin",
            local_path=src,
            show_progress=False,
        )
        url = storage.presigned_url(
            bucket=NimbusBucketType.DATASETS,
            project=PROJECT,
            key="folder/object.bin",
            expires_in=600,
        )
        assert url.startswith("http")
        assert storage.config.bucket_name(NimbusBucketType.DATASETS) in url
        assert f"{PROJECT}/folder/object.bin" in url

    def test_invalid_expires_in_raises(self, storage: NimbusCloudStorage) -> None:
        with pytest.raises(NimbusValidationError):
            storage.presigned_url(
                bucket=NimbusBucketType.DATASETS,
                project=PROJECT,
                key="a.bin",
                expires_in=0,
            )


class TestErrorMapping:
    def test_head_object_other_error_raises_storage_error(
        self, storage: NimbusCloudStorage
    ) -> None:
        def boom(*_args: object, **_kwargs: object) -> None:
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "HeadObject")

        storage.client.head_object = boom  # type: ignore[method-assign]
        with pytest.raises(NimbusStorageError):
            storage.exists(bucket=NimbusBucketType.DATASETS, project=PROJECT, key="anything.bin")
