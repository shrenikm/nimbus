# nimbus

A small, project-agnostic Python package for storing files on S3-compatible
object storage (Cloudflare R2, Backblaze B2, AWS S3, MinIO, …).
It wraps `boto3` with a tiny opinionated API — upload, download, list, exists,
delete, presigned URLs — keyed by a `(bucket_type, project, key)` triple. All
provider-specific details (endpoint, credentials, bucket naming) come from
environment variables; the package itself contains no hardcoded credentials,
no hardcoded bucket names, and no references to any specific downstream user.

## Installation

```
pip install "nimbus @ git+https://github.com/shrenikm/nimbus.git@main"
```

For development:

```
git clone https://github.com/shrenikm/nimbus.git
cd nimbus
pip install -e ".[dev]"
```

Python 3.12 or newer is required.

## Configuration

Nimbus reads configuration from environment variables. A `.env` file in the
current working directory is loaded automatically; see `.env.example` for the
full list. The minimum required vars:

| Variable                | Purpose                                                  |
|-------------------------|----------------------------------------------------------|
| `R2_ENDPOINT_URL`       | Full S3-compatible endpoint URL.                         |
| `R2_ACCOUNT_ID`         | Alternative — used to build the R2 endpoint URL.         |
| `R2_ACCESS_KEY_ID`      | Access key.                                              |
| `R2_SECRET_ACCESS_KEY`  | Secret key.                                              |

Optional per-bucket overrides:

| Variable                       | Purpose                                              |
|--------------------------------|------------------------------------------------------|
| `NIMBUS_BUCKET_RAW_DATA`       | Override bucket name for the `raw-data` category.    |
| `NIMBUS_BUCKET_DATASETS`       | Override bucket name for the `datasets` category.    |
| `NIMBUS_BUCKET_CHECKPOINTS`    | Override bucket name for the `checkpoints` category. |
| `NIMBUS_BUCKET_TEST`           | Override bucket name for the `test` category.        |

By default the four buckets are named `nimbus-raw-data`, `nimbus-datasets`,
`nimbus-checkpoints`, and `nimbus-test`. Buckets must already exist on the
provider — nimbus does not create or delete buckets.

All buckets are expected to be private. Nimbus never enables public access
or generates public links; use presigned URLs for short-lived sharing.

## Bucket types

Four categories ship with the package, all `StrEnum` values:

```python
from nimbus import NimbusBucketType

NimbusBucketType.RAW_DATA      # "raw-data"     general/curated raw data
NimbusBucketType.DATASETS      # "datasets"     processed datasets
NimbusBucketType.CHECKPOINTS   # "checkpoints"  model checkpoints
NimbusBucketType.TEST          # "test"         used only by the integration suite
```

`TEST` is reserved for the integration tests in this package and exists so
that test artifacts never share a bucket with real data.

Because `NimbusBucketType` is a `StrEnum`, every API also accepts plain strings.
If you maintain your own taxonomy, just pass strings and configure the
matching `NIMBUS_BUCKET_*` overrides.

## Programmatic API

```python
from nimbus import NimbusBucketType, NimbusCloudConfig, NimbusCloudStorage

config = NimbusCloudConfig.from_env()
storage = NimbusCloudStorage(config)

storage.upload_file(
    bucket=NimbusBucketType.CHECKPOINTS,
    project="my-project",
    key="run-2026-05-16/best.pth",
    local_path="./best.pth",
)

storage.download_file(
    bucket=NimbusBucketType.CHECKPOINTS,
    project="my-project",
    key="run-2026-05-16/best.pth",
    local_path="./best.pth",
)

storage.upload_dir(
    bucket=NimbusBucketType.DATASETS,
    project="shared",
    key_prefix="my-dataset-v1/",
    local_dir="./my-dataset/",
)

for key in storage.list_keys(bucket=NimbusBucketType.DATASETS, project="shared"):
    print(key)

assert storage.exists(
    bucket=NimbusBucketType.CHECKPOINTS,
    project="my-project",
    key="run-2026-05-16/best.pth",
)

storage.delete(
    bucket=NimbusBucketType.CHECKPOINTS,
    project="my-project",
    key="run-2026-05-16/old.pth",
)

url = storage.presigned_url(
    bucket=NimbusBucketType.DATASETS,
    project="shared",
    key="my-dataset-v1/sample.parquet",
    expires_in=3600,
)
```

Object keys are always composed as `{project}/{key}`. The inner structure
beneath the project prefix is entirely up to the caller — nimbus enforces
only that the project name is DNS-safe and the key is non-empty and free of
control characters.

## CLI

The package installs a `nimbus` console entry point:

```
nimbus upload   <bucket-type> <project> <key> <local-path>
nimbus download <bucket-type> <project> <key> <local-path>
nimbus ls       <bucket-type> <project> [<key-prefix>]
nimbus exists   <bucket-type> <project> <key>
nimbus rm       <bucket-type> <project> <key>
nimbus presign  <bucket-type> <project> <key> [--expires 3600]
```

`<bucket-type>` is one of `raw-data | datasets | checkpoints | test`. Examples:

```
nimbus upload checkpoints my-project run-abc/best.pth ./best.pth
nimbus ls datasets shared
nimbus presign datasets shared my-dataset-v1/sample.parquet --expires 7200
```

`nimbus exists` exits 0 when the object is present and 1 when it is not.

## Transfer defaults

Uploads and downloads use the following `boto3` `TransferConfig`:

| Setting                | Value   |
|------------------------|---------|
| `multipart_threshold`  | 50 MiB  |
| `multipart_chunksize`  | 50 MiB  |
| `max_concurrency`      | 10      |
| `use_threads`          | `True`  |

A `tqdm` progress bar is shown by default for both directions; pass
`show_progress=False` (or `--no-progress` on the CLI) to suppress it.

## Testing

```
pytest                                  # unit tests only (moto-mocked, fully offline)
NIMBUS_INTEGRATION_TESTS=1 pytest -m integration  # opt-in real-bucket tests
```

The integration suite requires valid credentials. It always writes to the
`test` bucket (default `nimbus-test`) under the `integration-tests` project
namespace, using unique keys under `itest/...` and cleaning up after itself.
It will not touch any other bucket.

## License

MIT — see [LICENSE](LICENSE).
