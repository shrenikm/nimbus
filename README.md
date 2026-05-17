# nimbus

A small, project-agnostic Python package for storing files on S3-compatible
object storage (Cloudflare R2, Backblaze B2, AWS S3, MinIO, …). It wraps
`boto3` with a tiny opinionated API — upload, download, list, exists,
delete, presigned URLs, plus matching directory operations — keyed by a
`(bucket_type, project, key)` triple.

## Documentation

**Full docs: <https://shrenikm.github.io/nimbus/>**

- [Getting started](https://shrenikm.github.io/nimbus/getting-started/) — install, R2 setup, environment variables.
- [Bucket types](https://shrenikm.github.io/nimbus/bucket-types/) — the four categories and how they resolve.
- [CLI reference](https://shrenikm.github.io/nimbus/cli/) — every command, with examples.
- [API reference](https://shrenikm.github.io/nimbus/api/) — auto-generated.
- [Testing](https://shrenikm.github.io/nimbus/testing/) — unit and integration workflow.

## Quick install

```
pip install "nimbus @ git+https://github.com/shrenikm/nimbus.git@main"
```

Python 3.12 or newer.

## Quick example

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

See the [docs](https://shrenikm.github.io/nimbus/) for everything else.

## License

MIT — see [LICENSE](LICENSE).
