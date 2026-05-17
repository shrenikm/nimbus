"""
High-level interface to S3-compatible object storage.

NimbusCloudStorage takes a NimbusCloudConfig, builds a boto3 client, and exposes the
small set of operations nimbus is meant for: upload, download, list, exists,
delete, and presigned URLs.
"""

from __future__ import annotations

import concurrent.futures
import os
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import attrs
from boto3.exceptions import Boto3Error, S3UploadFailedError
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
from tqdm import tqdm

from nimbus.bucket import NimbusBucketType
from nimbus.client import build_s3_client
from nimbus.config import NimbusCloudConfig
from nimbus.exceptions import (
    NimbusObjectNotFoundError,
    NimbusStorageError,
    NimbusValidationError,
)
from nimbus.paths import join_key, normalize_prefix, validate_project_name
from nimbus.progress import NimbusProgressCallback

_T = TypeVar("_T")

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    S3Client = Any

MB = 1024 * 1024
DEFAULT_MULTIPART_THRESHOLD = 50 * MB
DEFAULT_MULTIPART_CHUNKSIZE = 50 * MB
DEFAULT_MAX_CONCURRENCY = 10

# Concurrent files for upload_dir / download_dir. Independent from
# DEFAULT_MAX_CONCURRENCY, which is per-file multipart-chunk concurrency.
DEFAULT_MAX_DIR_WORKERS = 8

DEFAULT_PRESIGN_EXPIRES_IN = 3600

_NOT_FOUND_CODES = frozenset({"404", "NoSuchKey", "NoSuchBucket", "NotFound"})


def default_transfer_config() -> TransferConfig:
    """
    Construct the TransferConfig used by all uploads and downloads.
    """
    return TransferConfig(
        multipart_threshold=DEFAULT_MULTIPART_THRESHOLD,
        multipart_chunksize=DEFAULT_MULTIPART_CHUNKSIZE,
        max_concurrency=DEFAULT_MAX_CONCURRENCY,
        use_threads=True,
    )


def _client_error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def _is_not_found(exc: ClientError) -> bool:
    code = _client_error_code(exc)
    if code in _NOT_FOUND_CODES:
        return True
    status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return status == 404


@attrs.define(slots=True, eq=False)
class NimbusCloudStorage:
    """
    Façade over a boto3 S3 client scoped to a single NimbusCloudConfig.

    Methods accept either a NimbusBucketType enum member or a raw string for
    bucket; project is always a plain string chosen by the caller; key is
    the per-object path inside the project namespace.
    """

    config: NimbusCloudConfig
    _client: S3Client = attrs.field(init=False)
    _transfer_config: TransferConfig = attrs.field(init=False, factory=default_transfer_config)

    def __attrs_post_init__(self) -> None:
        self._client = build_s3_client(self.config)

    @property
    def client(self) -> S3Client:
        """
        Underlying boto3 S3 client, exposed for advanced callers.
        """
        return self._client

    def upload_file(
        self,
        *,
        bucket: NimbusBucketType | str,
        project: str,
        key: str,
        local_path: str | os.PathLike[str],
        show_progress: bool = True,
        extra_args: dict[str, Any] | None = None,
    ) -> str:
        """
        Upload a single local file. Returns the resolved object key.
        """
        bucket_name = self.config.bucket_name(bucket)
        object_key = join_key(project, key)
        path = Path(local_path)
        if not path.is_file():
            raise NimbusValidationError(f"local_path is not a file: {path}")

        callback: NimbusProgressCallback | None = None
        if show_progress:
            callback = NimbusProgressCallback(total_bytes=path.stat().st_size, description=object_key)
        try:
            self._client.upload_file(
                Filename=str(path),
                Bucket=bucket_name,
                Key=object_key,
                ExtraArgs=extra_args,
                Config=self._transfer_config,
                Callback=callback,
            )
        except (ClientError, S3UploadFailedError, Boto3Error) as exc:
            raise NimbusStorageError(f"upload failed for s3://{bucket_name}/{object_key}: {exc}") from exc
        finally:
            if callback is not None:
                callback.close()
        return object_key

    def download_file(
        self,
        *,
        bucket: NimbusBucketType | str,
        project: str,
        key: str,
        local_path: str | os.PathLike[str],
        show_progress: bool = True,
    ) -> Path:
        """
        Download an object to a local file, creating parent directories as needed.
        """
        bucket_name = self.config.bucket_name(bucket)
        object_key = join_key(project, key)
        destination = Path(local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        total_bytes = 0
        if show_progress:
            total_bytes = self._object_size(bucket_name, object_key)

        callback: NimbusProgressCallback | None = None
        if show_progress:
            callback = NimbusProgressCallback(total_bytes=total_bytes, description=object_key)
        try:
            self._client.download_file(
                Bucket=bucket_name,
                Key=object_key,
                Filename=str(destination),
                Config=self._transfer_config,
                Callback=callback,
            )
        except ClientError as exc:
            if _is_not_found(exc):
                raise NimbusObjectNotFoundError(f"object not found: s3://{bucket_name}/{object_key}") from exc
            raise NimbusStorageError(f"download failed for s3://{bucket_name}/{object_key}: {exc}") from exc
        except Boto3Error as exc:
            raise NimbusStorageError(f"download failed for s3://{bucket_name}/{object_key}: {exc}") from exc
        finally:
            if callback is not None:
                callback.close()
        return destination

    def upload_dir(
        self,
        *,
        bucket: NimbusBucketType | str,
        project: str,
        local_dir: str | os.PathLike[str],
        key_prefix: str = "",
        show_progress: bool = True,
        extra_args: dict[str, Any] | None = None,
        max_workers: int = DEFAULT_MAX_DIR_WORKERS,
    ) -> list[str]:
        """
        Recursively upload every file under local_dir, with concurrent
        per-file transfers.

        The local directory itself is NOT part of the key — only its
        contents are mapped under key_prefix. Same semantics as
        `rsync local_dir/ dest/` or `aws s3 sync local_dir/ s3://...`.

        Example: given the local tree

            a/
            ├── c.txt
            └── b/
                └── d.txt

        calling upload_dir(project="P", local_dir="a/", key_prefix="z/")
        produces these object keys:

            P/z/c.txt
            P/z/b/d.txt

        (NOT P/z/a/c.txt — the "a" directory name is stripped.)

        An empty key_prefix uploads files directly under the project
        namespace (P/c.txt, P/b/d.txt). Returns the list of resolved
        object keys in deterministic (submission) order, regardless of
        the order in which the concurrent transfers complete.

        max_workers controls how many files upload in parallel; the
        per-file multipart concurrency (DEFAULT_MAX_CONCURRENCY) is
        independent of this.
        """
        validate_project_name(project)
        source = Path(local_dir)
        if not source.is_dir():
            raise NimbusValidationError(f"local_dir is not a directory: {source}")

        normalized_prefix = normalize_prefix(key_prefix)
        if normalized_prefix and not normalized_prefix.endswith("/"):
            normalized_prefix = f"{normalized_prefix}/"

        plan: list[tuple[Path, str]] = []
        for file_path in sorted(p for p in source.rglob("*") if p.is_file()):
            relative = file_path.relative_to(source).as_posix()
            per_file_key = f"{normalized_prefix}{relative}" if normalized_prefix else relative
            plan.append((file_path, per_file_key))

        def _upload_one(file_path: Path, per_file_key: str) -> str:
            return self.upload_file(
                bucket=bucket,
                project=project,
                key=per_file_key,
                local_path=file_path,
                show_progress=False,
                extra_args=extra_args,
            )

        return self._run_dir_transfers(
            plan=plan,
            worker=_upload_one,
            max_workers=max_workers,
            show_progress=show_progress,
            description=f"uploading to {self.config.bucket_name(bucket)}/{project}",
        )

    def download_dir(
        self,
        *,
        bucket: NimbusBucketType | str,
        project: str,
        local_dir: str | os.PathLike[str],
        key_prefix: str = "",
        show_progress: bool = True,
        max_workers: int = DEFAULT_MAX_DIR_WORKERS,
    ) -> list[Path]:
        """
        Download every object under {project}/{key_prefix} into local_dir,
        with concurrent per-file transfers, preserving the key structure
        beneath the prefix.

        local_dir is the destination root — neither the project name nor
        the prefix is added as an extra subdirectory. Exact mirror of
        upload_dir: upload_dir(local_dir=L, key_prefix=P) followed by
        download_dir(local_dir=L, key_prefix=P) round-trips cleanly.

        Example: if the bucket contains

            P/z/c.txt
            P/z/b/d.txt

        calling download_dir(project="P", local_dir="out/", key_prefix="z/")
        writes:

            out/
            ├── c.txt
            └── b/
                └── d.txt

        (NOT out/z/c.txt — the prefix is stripped from each key before
        joining onto local_dir.)

        An empty key_prefix downloads the entire project and preserves
        the full key structure (out/z/c.txt, out/z/b/d.txt above).
        Returns the list of local Paths written in deterministic
        (submission) order. max_workers controls per-file concurrency.
        """
        validate_project_name(project)
        normalized_prefix = normalize_prefix(key_prefix)
        if normalized_prefix and not normalized_prefix.endswith("/"):
            normalized_prefix = f"{normalized_prefix}/"

        dest_root = Path(local_dir)
        dest_root.mkdir(parents=True, exist_ok=True)

        plan: list[tuple[str, Path]] = []
        for project_relative_key in self.list_keys(bucket=bucket, project=project, key_prefix=normalized_prefix):
            if normalized_prefix and project_relative_key.startswith(normalized_prefix):
                local_relative = project_relative_key[len(normalized_prefix) :]
            else:
                local_relative = project_relative_key
            if not local_relative:
                continue
            plan.append((project_relative_key, dest_root / local_relative))

        def _download_one(project_relative_key: str, dest_path: Path) -> Path:
            return self.download_file(
                bucket=bucket,
                project=project,
                key=project_relative_key,
                local_path=dest_path,
                show_progress=False,
            )

        return self._run_dir_transfers(
            plan=plan,
            worker=_download_one,
            max_workers=max_workers,
            show_progress=show_progress,
            description=f"downloading from {self.config.bucket_name(bucket)}/{project}",
        )

    def list_keys(
        self,
        *,
        bucket: NimbusBucketType | str,
        project: str,
        key_prefix: str = "",
    ) -> Iterator[str]:
        """
        Yield object keys (with project prefix stripped) for everything under
        `{project}/{key_prefix}`. Streams via paginator so large buckets are
        fine.
        """
        validate_project_name(project)
        normalized_prefix = normalize_prefix(key_prefix)
        bucket_name = self.config.bucket_name(bucket)
        full_prefix = f"{project}/{normalized_prefix}" if normalized_prefix else f"{project}/"

        paginator = self._client.get_paginator("list_objects_v2")
        try:
            pages = paginator.paginate(Bucket=bucket_name, Prefix=full_prefix)
            for page in pages:
                for obj in page.get("Contents", []) or []:
                    raw_key: str = obj["Key"]
                    if raw_key.startswith(f"{project}/"):
                        yield raw_key[len(project) + 1 :]
                    else:
                        yield raw_key
        except ClientError as exc:
            raise NimbusStorageError(f"list failed for s3://{bucket_name}/{full_prefix}: {exc}") from exc

    def exists(
        self,
        *,
        bucket: NimbusBucketType | str,
        project: str,
        key: str,
    ) -> bool:
        """
        Return True iff the object is present.
        """
        bucket_name = self.config.bucket_name(bucket)
        object_key = join_key(project, key)
        try:
            self._client.head_object(Bucket=bucket_name, Key=object_key)
        except ClientError as exc:
            if _is_not_found(exc):
                return False
            raise NimbusStorageError(f"head failed for s3://{bucket_name}/{object_key}: {exc}") from exc
        return True

    def delete(
        self,
        *,
        bucket: NimbusBucketType | str,
        project: str,
        key: str,
    ) -> None:
        """
        Delete a single object. Succeeds silently if the object is already gone.
        """
        bucket_name = self.config.bucket_name(bucket)
        object_key = join_key(project, key)
        try:
            self._client.delete_object(Bucket=bucket_name, Key=object_key)
        except ClientError as exc:
            raise NimbusStorageError(f"delete failed for s3://{bucket_name}/{object_key}: {exc}") from exc

    def purge_test_bucket(self) -> int:
        """
        Delete every object in the TEST bucket, across every project namespace.
        Returns the number of objects deleted.

        Hardcoded to NimbusBucketType.TEST. There is intentionally no way to
        point this method at any other bucket — bulk deletion against
        raw-data, datasets, or checkpoints is not exposed by this package.
        """
        bucket_name = self.config.bucket_name(NimbusBucketType.TEST)
        paginator = self._client.get_paginator("list_objects_v2")
        deleted = 0
        try:
            for page in paginator.paginate(Bucket=bucket_name):
                contents = page.get("Contents", []) or []
                if not contents:
                    continue
                # delete_objects accepts up to 1000 keys per call, which matches the paginator's default page size.
                objects = [{"Key": obj["Key"]} for obj in contents]
                self._client.delete_objects(
                    Bucket=bucket_name,
                    Delete={"Objects": objects, "Quiet": True},
                )
                deleted += len(objects)
        except ClientError as exc:
            raise NimbusStorageError(f"bulk delete failed for s3://{bucket_name}: {exc}") from exc
        return deleted

    def presigned_url(
        self,
        *,
        bucket: NimbusBucketType | str,
        project: str,
        key: str,
        expires_in: int = DEFAULT_PRESIGN_EXPIRES_IN,
        http_method: str = "get_object",
    ) -> str:
        """
        Generate a time-limited URL for the object. http_method is the boto3
        client-method name (default is get_object, i.e. a presigned GET).
        """
        if expires_in <= 0:
            raise NimbusValidationError(f"expires_in must be positive, got {expires_in}")
        bucket_name = self.config.bucket_name(bucket)
        object_key = join_key(project, key)
        try:
            return self._client.generate_presigned_url(
                ClientMethod=http_method,
                Params={"Bucket": bucket_name, "Key": object_key},
                ExpiresIn=expires_in,
            )
        except ClientError as exc:
            raise NimbusStorageError(f"presign failed for s3://{bucket_name}/{object_key}: {exc}") from exc

    def _run_dir_transfers(
        self,
        *,
        plan: list[tuple[Any, ...]],
        worker: Callable[..., _T],
        max_workers: int,
        show_progress: bool,
        description: str,
    ) -> list[_T]:
        """
        Run worker(*args) for each tuple in plan, on a ThreadPoolExecutor with
        max_workers workers. Returns results in submission order, regardless
        of completion order. First worker exception cancels pending tasks and
        propagates.
        """
        if max_workers < 1:
            raise NimbusValidationError(f"max_workers must be >= 1, got {max_workers}")
        if not plan:
            return []

        results: list[_T | None] = [None] * len(plan)
        bar = (
            tqdm(total=len(plan), unit="file", desc=description, leave=False, dynamic_ncols=True)
            if show_progress
            else None
        )
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_index = {executor.submit(worker, *args): index for index, args in enumerate(plan)}
                try:
                    for future in concurrent.futures.as_completed(future_to_index):
                        results[future_to_index[future]] = future.result()
                        if bar is not None:
                            bar.update(1)
                except BaseException:
                    for pending in future_to_index:
                        pending.cancel()
                    raise
        finally:
            if bar is not None:
                bar.close()
        return results  # type: ignore[return-value]

    def _object_size(self, bucket_name: str, object_key: str) -> int:
        """
        Look up an object's size in bytes via HEAD. Raises
        NimbusObjectNotFoundError if the object is missing.
        """
        try:
            response = self._client.head_object(Bucket=bucket_name, Key=object_key)
        except ClientError as exc:
            if _is_not_found(exc):
                raise NimbusObjectNotFoundError(f"object not found: s3://{bucket_name}/{object_key}") from exc
            raise NimbusStorageError(f"head failed for s3://{bucket_name}/{object_key}: {exc}") from exc
        return int(response.get("ContentLength", 0))
