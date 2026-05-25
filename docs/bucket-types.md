# Bucket types

Nimbus addresses storage with a three-part key: **bucket type**, **project
namespace**, and **object key**. The final S3 key is always
`{project}/{key}`; the underlying bucket name is derived from the bucket
type.

## The five categories

```python
from nimbus import NimbusBucketType

NimbusBucketType.RAW_DATA      # "raw-data"     → bucket nimbus-raw-data
NimbusBucketType.DATASETS      # "datasets"     → bucket nimbus-datasets
NimbusBucketType.CHECKPOINTS   # "checkpoints"  → bucket nimbus-checkpoints
NimbusBucketType.APP_DATA      # "app-data"     → bucket nimbus-app-data
NimbusBucketType.TEST          # "test"         → bucket nimbus-test
```

By default, bucket names are derived from the enum value as
`{prefix}-{value}` with `prefix="nimbus"`. Each can be replaced with an
arbitrary full bucket name via env var — see [Per-bucket name
overrides](getting-started.md#per-bucket-name-overrides) for the five
variables (`NIMBUS_BUCKET_RAW_DATA`, etc.). Overrides are full names,
not suffixes — the `nimbus-` prefix is *not* prepended.

`NimbusBucketType` is a `StrEnum`, so every API call also accepts the raw
string form (`"checkpoints"` is interchangeable with
`NimbusBucketType.CHECKPOINTS`).

## What each category is for

| Category | Intended contents |
|---|---|
| `raw-data` | Raw inputs that are written once and rarely modified. |
| `datasets` | Processed / curated datasets ready for training. |
| `checkpoints` | Model checkpoints and training artifacts. |
| `app-data` | Generic application data (DB snapshots, exported config, generated artifacts). The specific nature lives in the key path. |
| `test` | **Reserved for the integration test suite.** Don't put real data here. |

These are conventions, not hard rules — the package treats all five
identically at the storage layer. The category split exists so that
buckets can be lifecycled and budgeted independently on the provider side
(e.g., aggressive retention on `test`, none on `raw-data`).

## The TEST bucket is special

`NimbusBucketType.TEST` is reserved for nimbus's own integration tests
and any ad-hoc smoke testing you do. The package exposes one bulk-delete
operation, [`purge_test_bucket()`][nimbus.storage.NimbusCloudStorage.purge_test_bucket],
which is **hardcoded to TEST** at the API level — it accepts no `bucket`
argument and cannot be aimed at any other category. This is deliberate:
there's no syntactic way to accidentally nuke `nimbus-checkpoints` from
a script.

If you override `NIMBUS_BUCKET_TEST` to point at a custom bucket,
`purge_test_bucket()` will operate on *that* bucket. The safety guarantee
is "only the bucket type you've configured as TEST", not "literally the
bucket named nimbus-test".

## Key composition

Every object in nimbus is addressed by `(bucket_type, project, key)`:

- **project** — a top-level namespace inside the bucket. Must match the
  pattern `[a-z0-9][a-z0-9._-]{0,62}` (DNS-style).
- **key** — everything below the project. Free-form, but cannot be empty
  or start with `/`.

The final S3 object key is `{project}/{key}`. So:

```python
storage.upload_file(
    bucket=NimbusBucketType.CHECKPOINTS,   # bucket: nimbus-checkpoints
    project="my-project",                   #
    key="run-2026-05-16/best.pth",          # full S3 key:
    local_path="./best.pth",                #   nimbus-checkpoints/my-project/run-2026-05-16/best.pth
)
```

The structure beneath the project namespace is entirely up to the
caller — nimbus doesn't impose run-ID schemes, date folders, or version
tags.

## Privacy

All five buckets are expected to be **private**. Nimbus never enables
public bucket access, never generates `r2.dev`-style public URLs, and
never sets public ACLs. For short-lived sharing, use
[presigned URLs][nimbus.storage.NimbusCloudStorage.presigned_url].
