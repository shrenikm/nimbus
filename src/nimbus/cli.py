"""
Click-based command-line interface for nimbus.

Console entry point is registered as `nimbus` in pyproject.toml.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

import click

from nimbus.bucket import NimbusBucketType
from nimbus.config import NimbusCloudConfig
from nimbus.exceptions import NimbusError
from nimbus.storage import DEFAULT_PRESIGN_EXPIRES_IN, NimbusCloudStorage

BUCKET_TYPE_VALUES: tuple[str, ...] = tuple(b.value for b in NimbusBucketType)
BUCKET_TYPE_CHOICE = click.Choice(BUCKET_TYPE_VALUES, case_sensitive=False)


def _build_storage() -> NimbusCloudStorage:
    return NimbusCloudStorage(NimbusCloudConfig.from_env())


@click.group(
    help=(
        "nimbus: small CLI for storing files on S3-compatible object storage. "
        "Buckets are addressed by a bucket-type / project / key triple."
    )
)
@click.version_option(package_name="nimbus")
def main() -> None:
    """
    Top-level command group.
    """


@main.command("upload", help="Upload a local file to <bucket-type>/<project>/<key>.")
@click.argument("bucket_type", type=BUCKET_TYPE_CHOICE)
@click.argument("project", type=str)
@click.argument("key", type=str)
@click.argument("local_path", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option("--no-progress", "no_progress", is_flag=True, help="Suppress the tqdm progress bar.")
def upload_command(
    bucket_type: str, project: str, key: str, local_path: str, no_progress: bool
) -> None:
    storage = _build_storage()
    object_key = storage.upload_file(
        bucket=NimbusBucketType(bucket_type.lower()),
        project=project,
        key=key,
        local_path=local_path,
        show_progress=not no_progress,
    )
    bucket_name = storage.config.bucket_name(NimbusBucketType(bucket_type.lower()))
    click.echo(f"uploaded s3://{bucket_name}/{object_key}")


@main.command("download", help="Download an object to a local file.")
@click.argument("bucket_type", type=BUCKET_TYPE_CHOICE)
@click.argument("project", type=str)
@click.argument("key", type=str)
@click.argument("local_path", type=click.Path(dir_okay=False, writable=True))
@click.option("--no-progress", "no_progress", is_flag=True, help="Suppress the tqdm progress bar.")
def download_command(
    bucket_type: str, project: str, key: str, local_path: str, no_progress: bool
) -> None:
    storage = _build_storage()
    destination = storage.download_file(
        bucket=NimbusBucketType(bucket_type.lower()),
        project=project,
        key=key,
        local_path=local_path,
        show_progress=not no_progress,
    )
    click.echo(f"downloaded to {destination}")


@main.command("ls", help="List keys under a project (optionally filtered by key prefix).")
@click.argument("bucket_type", type=BUCKET_TYPE_CHOICE)
@click.argument("project", type=str)
@click.argument("key_prefix", type=str, required=False, default="")
def ls_command(bucket_type: str, project: str, key_prefix: str) -> None:
    storage = _build_storage()
    keys = storage.list_keys(
        bucket=NimbusBucketType(bucket_type.lower()), project=project, key_prefix=key_prefix
    )
    for object_key in keys:
        click.echo(object_key)


@main.command("exists", help="Check whether an object exists (exit 0 if yes, 1 if no).")
@click.argument("bucket_type", type=BUCKET_TYPE_CHOICE)
@click.argument("project", type=str)
@click.argument("key", type=str)
def exists_command(bucket_type: str, project: str, key: str) -> None:
    storage = _build_storage()
    present = storage.exists(bucket=NimbusBucketType(bucket_type.lower()), project=project, key=key)
    click.echo("yes" if present else "no")
    if not present:
        sys.exit(1)


@main.command("rm", help="Delete an object.")
@click.argument("bucket_type", type=BUCKET_TYPE_CHOICE)
@click.argument("project", type=str)
@click.argument("key", type=str)
def rm_command(bucket_type: str, project: str, key: str) -> None:
    storage = _build_storage()
    storage.delete(bucket=NimbusBucketType(bucket_type.lower()), project=project, key=key)
    click.echo(f"deleted {project}/{key}")


@main.command("presign", help="Generate a presigned URL for an object.")
@click.argument("bucket_type", type=BUCKET_TYPE_CHOICE)
@click.argument("project", type=str)
@click.argument("key", type=str)
@click.option(
    "--expires",
    "expires_in",
    type=int,
    default=DEFAULT_PRESIGN_EXPIRES_IN,
    show_default=True,
    help="Lifetime of the URL in seconds.",
)
def presign_command(bucket_type: str, project: str, key: str, expires_in: int) -> None:
    storage = _build_storage()
    url = storage.presigned_url(
        bucket=NimbusBucketType(bucket_type.lower()),
        project=project,
        key=key,
        expires_in=expires_in,
    )
    click.echo(url)


def run(argv: Sequence[str] | None = None) -> int:
    """
    Programmatic entry point that catches NimbusError and turns it into a
    non-zero exit code with a clean message (used by tests and embedders).
    """
    try:
        main.main(args=list(argv) if argv is not None else None, standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        return exc.exit_code
    except NimbusError as exc:
        click.echo(f"error: {exc}", err=True)
        return 1
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(run())
