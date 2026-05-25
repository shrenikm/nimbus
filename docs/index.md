# nimbus

A small, project-agnostic Python package for storing files on S3-compatible
object storage (Cloudflare R2, Backblaze B2, AWS S3, MinIO, …).

It wraps `boto3` with a tiny opinionated API — upload, download, list,
exists, delete, presigned URLs, plus matching directory operations —
keyed by a `(bucket_type, project, key)` triple. All provider-specific
details (endpoint, credentials, bucket naming) come from environment
variables; the package itself contains no hardcoded credentials and no
references to any specific downstream user.

## At a glance

```python
from nimbus import NimbusBucketType, NimbusCloudConfig, NimbusCloudStorage

storage = NimbusCloudStorage(NimbusCloudConfig.from_env())

storage.upload_file(
    bucket=NimbusBucketType.CHECKPOINTS,
    project="my-project",
    key="run-2026-05-16/best.pth",
    local_path="./best.pth",
)
```

Or from the shell:

```
nimbus upload checkpoints my-project run-2026-05-16/best.pth ./best.pth
```

## Where to go next

- **[Getting started](getting-started.md)** — install, conda env, R2 setup, environment variables.
- **[Bucket types](bucket-types.md)** — the five categories and how names resolve.
- **[CLI reference](cli.md)** — every command, with examples.
- **[API reference](api.md)** — auto-generated from the source.
- **[Testing](testing.md)** — unit and integration test workflow.

## Design notes

- **Provider-agnostic.** Anything that speaks the S3 API works. Cloudflare R2
  is the reference target.
- **Private buckets only.** Nimbus never enables public access. Use presigned
  URLs for short-lived sharing.
- **Concurrent transfers built in.** Multi-file directory operations use a
  thread pool by default; single-file multipart uploads/downloads parallelize
  chunks internally via boto3.
- **MIT licensed.** [See LICENSE](https://github.com/shrenikm/nimbus/blob/main/LICENSE).
