"""
Typer + Rich command-line interface for nimbus.

Console entry point is registered as `nimbus` in pyproject.toml.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import click.exceptions
import typer
from rich.console import Console

from nimbus.bucket import NimbusBucketType
from nimbus.config import NimbusCloudConfig
from nimbus.exceptions import NimbusError, NimbusObjectNotFoundError
from nimbus.storage import DEFAULT_PRESIGN_EXPIRES_IN, NimbusCloudStorage

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}

app = typer.Typer(
    name="nimbus",
    help=(
        "nimbus: small CLI for storing files on S3-compatible object storage. "
        "Buckets are addressed by a bucket-type / project / key triple."
    ),
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
    context_settings=CONTEXT_SETTINGS,
)

console = Console()
error_console = Console(stderr=True, style="bold red")


def _build_storage() -> NimbusCloudStorage:
    return NimbusCloudStorage(NimbusCloudConfig.from_env())


BucketArg = Annotated[
    NimbusBucketType,
    typer.Argument(help="One of: raw-data | datasets | checkpoints | test.", show_default=False),
]
ProjectArg = Annotated[
    str,
    typer.Argument(help="Project namespace (top-level prefix inside the bucket).", show_default=False),
]
KeyArg = Annotated[
    str,
    typer.Argument(help="Object key relative to the project namespace.", show_default=False),
]
NoProgressOpt = Annotated[
    bool,
    typer.Option("--no-progress", help="Suppress the tqdm progress bar."),
]


@app.command(context_settings=CONTEXT_SETTINGS)
def upload(
    bucket_type: BucketArg,
    project: ProjectArg,
    key: KeyArg,
    local_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Local file to upload.",
            show_default=False,
        ),
    ],
    no_progress: NoProgressOpt = False,
) -> None:
    """
    Upload a local file to [bold]<bucket-type>/<project>/<key>[/bold].
    """
    storage = _build_storage()
    object_key = storage.upload_file(
        bucket=bucket_type,
        project=project,
        key=key,
        local_path=local_path,
        show_progress=not no_progress,
    )
    bucket_name = storage.config.bucket_name(bucket_type)
    console.print(f"[green]uploaded[/green] s3://{bucket_name}/{object_key}")


@app.command(context_settings=CONTEXT_SETTINGS)
def download(
    bucket_type: BucketArg,
    project: ProjectArg,
    key: KeyArg,
    local_path: Annotated[
        Path,
        typer.Argument(
            file_okay=True,
            dir_okay=False,
            writable=True,
            help="Destination file path.",
            show_default=False,
        ),
    ],
    no_progress: NoProgressOpt = False,
) -> None:
    """
    Download an object to a local file.
    """
    storage = _build_storage()
    destination = storage.download_file(
        bucket=bucket_type,
        project=project,
        key=key,
        local_path=local_path,
        show_progress=not no_progress,
    )
    console.print(f"[green]downloaded[/green] to {destination}")


@app.command("ls", context_settings=CONTEXT_SETTINGS)
def list_keys(
    bucket_type: BucketArg,
    project: ProjectArg,
    key_prefix: Annotated[
        str,
        typer.Argument(help="Optional key prefix to filter by.", show_default=False),
    ] = "",
) -> None:
    """
    List keys under a project (optionally filtered by key prefix).
    """
    storage = _build_storage()
    for object_key in storage.list_keys(bucket=bucket_type, project=project, key_prefix=key_prefix):
        console.print(object_key)


@app.command(context_settings=CONTEXT_SETTINGS)
def exists(bucket_type: BucketArg, project: ProjectArg, key: KeyArg) -> None:
    """
    Check whether an object exists (exits 0 if yes, 1 if no).
    """
    storage = _build_storage()
    present = storage.exists(bucket=bucket_type, project=project, key=key)
    if present:
        console.print("[green]yes[/green]")
        raise typer.Exit(code=0)
    console.print("[yellow]no[/yellow]")
    raise typer.Exit(code=1)


@app.command("rm", context_settings=CONTEXT_SETTINGS)
def remove(bucket_type: BucketArg, project: ProjectArg, key: KeyArg) -> None:
    """
    Delete an object.
    """
    storage = _build_storage()
    storage.delete(bucket=bucket_type, project=project, key=key)
    console.print(f"[green]deleted[/green] {project}/{key}")


@app.command(context_settings=CONTEXT_SETTINGS)
def presign(
    bucket_type: BucketArg,
    project: ProjectArg,
    key: KeyArg,
    expires: Annotated[
        int,
        typer.Option("--expires", help="Lifetime of the URL in seconds."),
    ] = DEFAULT_PRESIGN_EXPIRES_IN,
) -> None:
    """
    Generate a presigned URL for an object.
    """
    storage = _build_storage()
    url = storage.presigned_url(bucket=bucket_type, project=project, key=key, expires_in=expires)
    console.print(url, soft_wrap=True, highlight=False)


def main() -> int:
    """
    Entry point used by the console script.

    Catches NimbusError so credential / config / storage failures produce a
    clean message and a non-zero exit code instead of a traceback. Also
    catches click's Exit (raised by --help and no_args_is_help) and
    UsageError (raised by bad arguments) so they exit cleanly without a
    Rich traceback.
    """
    try:
        app(standalone_mode=False)
    except NimbusObjectNotFoundError as exc:
        error_console.print(f"not found: {exc}")
        return 2
    except NimbusError as exc:
        error_console.print(f"error: {exc}")
        return 1
    except click.exceptions.UsageError as exc:
        exc.show()
        return exc.exit_code
    except click.exceptions.Exit as exc:
        return int(exc.exit_code)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else (0 if exc.code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
