# API reference

All public symbols are exported from the top-level `nimbus` package:

```python
from nimbus import (
    NimbusBucketType,
    NimbusCloudConfig,
    NimbusCloudStorage,
    NimbusError,
    NimbusConfigError,
    NimbusValidationError,
    NimbusStorageError,
    NimbusObjectNotFoundError,
)
```

Everything below is auto-generated from the source.

---

## NimbusBucketType

::: nimbus.bucket.NimbusBucketType
    options:
      show_bases: false

---

## NimbusCloudConfig

::: nimbus.config.NimbusCloudConfig
    options:
      show_bases: false
      members:
        - from_env
        - bucket_name

---

## NimbusCloudStorage

::: nimbus.storage.NimbusCloudStorage
    options:
      show_bases: false
      members:
        - client
        - upload_file
        - download_file
        - upload_dir
        - download_dir
        - list_keys
        - exists
        - delete
        - presigned_url
        - purge_test_bucket

---

## Exceptions

All nimbus-raised errors inherit from `NimbusError`. Catch the family
with one `except NimbusError`, or distinguish by subclass.

::: nimbus.exceptions.NimbusError
    options:
      show_bases: false

::: nimbus.exceptions.NimbusConfigError
    options:
      show_bases: true

::: nimbus.exceptions.NimbusValidationError
    options:
      show_bases: true

::: nimbus.exceptions.NimbusStorageError
    options:
      show_bases: true

::: nimbus.exceptions.NimbusObjectNotFoundError
    options:
      show_bases: true

---

## Constants

The storage module also exports a few module-level constants for
introspection. They are not considered stable public API but are useful
for understanding default behavior.

| Constant | Value | Meaning |
|---|---|---|
| `nimbus.storage.DEFAULT_MULTIPART_THRESHOLD` | 50 MiB | Files larger than this use multipart upload. |
| `nimbus.storage.DEFAULT_MULTIPART_CHUNKSIZE` | 50 MiB | Multipart chunk size. |
| `nimbus.storage.DEFAULT_MAX_CONCURRENCY` | 10 | Per-file multipart-chunk concurrency (boto3 `TransferConfig`). |
| `nimbus.storage.DEFAULT_MAX_DIR_WORKERS` | 8 | Per-file concurrency for `upload_dir` / `download_dir`. |
| `nimbus.storage.DEFAULT_PRESIGN_EXPIRES_IN` | 3600 | Default presigned-URL lifetime, in seconds. |
| `nimbus.config.DEFAULT_BUCKET_PREFIX` | `"nimbus"` | Prefix combined with each `NimbusBucketType` value. |
