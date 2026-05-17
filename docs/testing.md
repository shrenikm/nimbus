# Testing

Nimbus has two test tiers: **unit** (offline, moto-mocked) and
**integration** (opt-in, hits a real S3-compatible bucket).

## Unit tests

```
pytest
```

Unit tests use [moto](https://github.com/getmoto/moto) to mock S3 entirely
in process — no credentials needed, no network calls, runs in a few
seconds. They cover the entire library API surface (upload, download,
list, exists, delete, presigned URLs, both directory operations,
`purge_test_bucket`), the CLI commands, and the `NimbusCloudConfig`
construction / env-loading paths.

### Hermetic environment

An autouse pytest fixture (`tests/conftest.py::_isolate_nimbus_env`)
strips every `R2_*` / `NIMBUS_*` env var and stubs out
`nimbus.config.load_dotenv` so unit tests stay reproducible even when a
real `.env` file sits in the project root.

The fixture **skips itself** for tests marked `integration`, which need
the real environment to talk to live R2.

## Integration tests

```
NIMBUS_INTEGRATION_TESTS=1 pytest -m integration
```

Or run both tiers together:

```
NIMBUS_INTEGRATION_TESTS=1 pytest
```

The integration suite requires valid R2 credentials in `.env`. It
**only ever touches** [`NimbusBucketType.TEST`][nimbus.bucket.NimbusBucketType]
under the `integration-tests` project namespace. Each test uses a unique
`itest/<timestamp>-<uuid>.bin` key and cleans up after itself on both
success and failure.

It will not touch any other bucket. There is no env knob to redirect it
elsewhere.

## Clearing the test bucket

If integration runs leave garbage behind (rare, but possible if a process
is killed mid-cleanup), wipe the test bucket with:

```
nimbus purge-test-bucket --yes
```

See [`purge_test_bucket`][nimbus.storage.NimbusCloudStorage.purge_test_bucket] for
why this is safe — the API is hardcoded to TEST and cannot be aimed
elsewhere.

## Linting and formatting

```
ruff check .
ruff format .
```

Both must pass cleanly before any change is merged. Configuration lives
in `pyproject.toml` (`[tool.ruff]`): line length 120, target Python 3.12,
the usual lint set (E, F, W, I, B, UP, SIM, C4, RUF).

## CI

Tests and lint don't currently run in CI, but the [docs deploy
workflow](https://github.com/shrenikm/nimbus/blob/main/.github/workflows/docs.yml)
does build the docs site on every push to `main`. If the docs fail to
build, the deploy is blocked.
