# AGENTS.md

## Generic-only rule

This package must stay project-agnostic. No references to any specific consumer project — in code, docstrings, examples, or tests. Project names are always plain strings passed in by callers; never add an enum for them. Examples in docs use placeholders like `my-project`, `my-dataset`.

## Naming convention

Public classes are prefixed with `Nimbus` (`NimbusBucketType`, `NimbusCloudConfig`, `NimbusCloudStorage`, `NimbusProgressCallback`, the `NimbusError` family). Modules, module-level constants, and free functions are not. Follow this when adding new public surface.

## Public API surface

Only what `src/nimbus/__init__.py` exports is public. Everything else (env-name constants, `build_s3_client`, `default_transfer_config`, helpers in `paths.py`) is internal and may change without notice. Don't expand `__all__` casually.

## `NimbusBucketType.TEST` is special

- Reserved for integration tests. The integration test file hardcodes it; do not add an env knob to redirect.
- `NimbusCloudStorage.purge_test_bucket()` takes no `bucket` argument **on purpose**. The safety guarantee is that bulk deletion can never be aimed at `raw-data`, `datasets`, or `checkpoints`. Do not relax this signature or add a generic bulk-delete method.

## Bucket names are fixed

Final bucket names are always `{bucket_prefix}-{bucket_type.value}`, with `bucket_prefix` defaulting to `"nimbus"`.

## Test architecture

- Python 3.12+, pytest. All unit tests are moto-mocked (`tests/conftest.py::mocked_s3`) — fully offline, no credentials needed.
- Key fixtures (in `conftest.py`): `mocked_s3`, `cloud_config`, `storage` (pre-creates all buckets in moto), and `aws_credentials` (dummy creds so botocore doesn't pick up real ones).
- The autouse `_isolate_nimbus_env` fixture clears `R2_*` / `NIMBUS_*` env vars and stubs `nimbus.config.load_dotenv` so unit tests are hermetic even when a real `.env` is present. It **skips itself** for tests marked `integration`, which intentionally need the real env + `.env`.
- Integration tests live in `tests/integration/`, are marked `integration`, gated by `NIMBUS_INTEGRATION_TESTS=1`, and only ever touch the TEST bucket under the `integration-tests` project namespace. Each test uses a unique `itest/<timestamp>-<uuid>.bin` key with best-effort cleanup.

## Error mapping convention

- 404 / missing object → `NimbusObjectNotFoundError`
- other storage failures → `NimbusStorageError`
- caller mistakes (bad path, key, project name) → `NimbusValidationError`
- config / env problems → `NimbusConfigError`

`boto3.s3.transfer.upload_file` repackages `botocore.exceptions.ClientError` as `boto3.exceptions.S3UploadFailedError`. Catch both, plus `Boto3Error` generically — see how `upload_file` and `download_file` do it.

## CLI

- typer + rich. Shared `CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}` is applied to the app and every subcommand so `-h` works everywhere.
- Bare `nimbus` shows help via `no_args_is_help=True` and exits 2 (typer/click convention).
- `main()` catches `NimbusError`, `click.exceptions.UsageError`, and `click.exceptions.Exit` to prevent Rich tracebacks on expected control flow.
- New commands: define a `@app.command(context_settings=CONTEXT_SETTINGS)` function, use `Annotated[..., typer.Argument/Option(...)]` for params, write to `console` / `error_console`.

## Code style

- Ruff is law — `ruff check .` and `ruff format .` must both pass. Line length 120, target py312. Config in `pyproject.toml`.
- Frozen `attrs` classes (`@attrs.frozen` / `@attrs.define(...)`) preferred over `@dataclass`.
- Type hints required on every public function and method; module-level globals avoided.
- Custom exceptions only (the `NimbusError` family); catch specific exceptions, not bare `Exception`.
- Docstrings on classes and non-trivial functions; skip them on obvious getters/setters and test functions. No comments stating the obvious; only comments that explain *why* for non-obvious logic.

## Dev workflow

The conda env is named `nimbus` (Python 3.12). Common commands:

```
conda activate nimbus
uv pip install -e ".[dev]"          # install / reinstall after dep changes
ruff check . && ruff format .       # lint + format
pytest                              # unit tests only (offline)
NIMBUS_INTEGRATION_TESTS=1 pytest -m integration   # real R2 (needs .env)
NIMBUS_INTEGRATION_TESTS=1 pytest                  # everything
```

## Build / install

- Backend is hatchling (not setuptools).
- All runtime + dev dependencies are pinned with `==` in `pyproject.toml`. Bump deliberately, not casually.
- Prefer `uv pip install` over plain pip when installing locally.

## Out of scope

Nimbus reads and writes objects. It does **not**:
- create or delete buckets (the user does this once in the provider dashboard)
- enable public bucket access (never set ACLs to public; never generate `r2.dev`-style URLs; presigned URLs are the only sharing mechanism)
- offer a generic bulk-delete (`purge_test_bucket` is the only bulk delete and it's TEST-only)
