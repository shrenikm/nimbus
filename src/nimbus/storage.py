"""
High-level interface to S3-compatible object storage.

NimbusCloudStorage takes a NimbusCloudConfig, builds a boto3 client, and exposes the
small set of operations nimbus is meant for: upload, download, list, exists,
delete, and presigned URLs.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import attrs
from boto3.exceptions import Boto3Error, S3UploadFailedError
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError

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

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    S3Client = Any

MB = 1024 * 1024
DEFAULT_MULTIPART_THRESHOLD = 50 * MB
DEFAULT_MULTIPART_CHUNKSIZE = 50 * MB
DEFAULT_MAX_CONCURRENCY = 10

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
        key_prefix: str,
        local_dir: str | os.PathLike[str],
        show_progress: bool = True,
        extra_args: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Recursively upload every file under local_dir.

        The object key for each file is `key_prefix` + `<relative path>`. An
        empty key_prefix uploads files directly under the project namespace.
        Returns the list of resolved object keys, in upload order.
        """
        validate_project_name(project)
        source = Path(local_dir)
        if not source.is_dir():
            raise NimbusValidationError(f"local_dir is not a directory: {source}")

        normalized_prefix = normalize_prefix(key_prefix)
        if normalized_prefix and not normalized_prefix.endswith("/"):
            normalized_prefix = f"{normalized_prefix}/"

        uploaded: list[str] = []
        for file_path in sorted(p for p in source.rglob("*") if p.is_file()):
            relative = file_path.relative_to(source).as_posix()
            per_file_key = f"{normalized_prefix}{relative}" if normalized_prefix else relative
            uploaded.append(
                self.upload_file(
                    bucket=bucket,
                    project=project,
                    key=per_file_key,
                    local_path=file_path,
                    show_progress=show_progress,
                    extra_args=extra_args,
                )
            )
        return uploaded

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
