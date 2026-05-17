from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nimbus.bucket import NimbusBucketType
from nimbus.cli import app
from nimbus.config import NimbusCloudConfig
from nimbus.storage import NimbusCloudStorage
from tests.conftest import TEST_REGION

PROJECT = "my-project"


@pytest.fixture
def cli_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Populate the env vars NimbusCloudConfig.from_env() expects so the CLI can
    construct a config without a .env file.
    """
    monkeypatch.setenv("R2_ENDPOINT_URL", "https://s3.amazonaws.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "testing")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_storage(mocked_s3: None, cli_env: None) -> NimbusCloudStorage:
    config = NimbusCloudConfig(
        endpoint_url="https://s3.amazonaws.com",
        access_key_id="testing",
        secret_access_key="testing",
        region=TEST_REGION,
    )
    cs = NimbusCloudStorage(config)
    for bucket_type in NimbusBucketType:
        cs.client.create_bucket(Bucket=config.bucket_name(bucket_type))
    return cs


def test_upload_then_ls_then_download(runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"hello")

    upload_result = runner.invoke(
        app,
        ["upload", "checkpoints", PROJECT, "run/a.bin", str(src), "--no-progress"],
    )
    assert upload_result.exit_code == 0, upload_result.output
    assert f"{PROJECT}/run/a.bin" in upload_result.output

    ls_result = runner.invoke(app, ["ls", "checkpoints", PROJECT])
    assert ls_result.exit_code == 0
    assert "run/a.bin" in ls_result.output

    dest = tmp_path / "out.bin"
    download_result = runner.invoke(
        app,
        ["download", "checkpoints", PROJECT, "run/a.bin", str(dest), "--no-progress"],
    )
    assert download_result.exit_code == 0
    assert dest.read_bytes() == b"hello"


def test_exists_exit_codes(runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    cli_storage.upload_file(
        bucket=NimbusBucketType.CHECKPOINTS,
        project=PROJECT,
        key="present.bin",
        local_path=src,
        show_progress=False,
    )
    yes = runner.invoke(app, ["exists", "checkpoints", PROJECT, "present.bin"])
    assert yes.exit_code == 0
    assert "yes" in yes.output

    no = runner.invoke(app, ["exists", "checkpoints", PROJECT, "absent.bin"])
    assert no.exit_code == 1
    assert "no" in no.output


def test_rm_removes_object(runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    cli_storage.upload_file(
        bucket=NimbusBucketType.CHECKPOINTS,
        project=PROJECT,
        key="doomed.bin",
        local_path=src,
        show_progress=False,
    )
    result = runner.invoke(app, ["rm", "checkpoints", PROJECT, "doomed.bin"])
    assert result.exit_code == 0
    assert not cli_storage.exists(bucket=NimbusBucketType.CHECKPOINTS, project=PROJECT, key="doomed.bin")


def test_presign_outputs_url(runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    cli_storage.upload_file(
        bucket=NimbusBucketType.DATASETS,
        project=PROJECT,
        key="a.bin",
        local_path=src,
        show_progress=False,
    )
    result = runner.invoke(app, ["presign", "datasets", PROJECT, "a.bin", "--expires", "120"])
    assert result.exit_code == 0
    assert result.output.strip().startswith("http")


def test_bucket_type_choice_validation(runner: CliRunner) -> None:
    result = runner.invoke(app, ["ls", "not-a-bucket-type", PROJECT])
    assert result.exit_code != 0


def test_help_lists_all_commands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("upload", "download", "ls", "exists", "rm", "presign"):
        assert command in result.output


def test_short_help_flag_works(runner: CliRunner) -> None:
    result = runner.invoke(app, ["-h"])
    assert result.exit_code == 0
    assert "upload" in result.output


def test_short_help_flag_on_subcommand(runner: CliRunner) -> None:
    result = runner.invoke(app, ["upload", "-h"])
    assert result.exit_code == 0
    assert "bucket" in result.output.lower()


def test_no_args_shows_help(runner: CliRunner) -> None:
    result = runner.invoke(app, [])
    assert "upload" in result.output
    assert "download" in result.output


def test_upload_dir_then_download_dir_round_trip(
    runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path
) -> None:
    src = tmp_path / "src"
    (src / "nested").mkdir(parents=True)
    (src / "nested" / "a.bin").write_bytes(b"AAA")
    (src / "top.bin").write_bytes(b"TOP")

    upload_result = runner.invoke(
        app,
        [
            "upload-dir",
            "datasets",
            PROJECT,
            str(src),
            "--prefix",
            "release-v1/",
            "--no-progress",
        ],
    )
    assert upload_result.exit_code == 0, upload_result.output
    assert "uploaded 2 file(s)" in upload_result.output

    dest = tmp_path / "dest"
    download_result = runner.invoke(
        app,
        [
            "download-dir",
            "datasets",
            PROJECT,
            str(dest),
            "--prefix",
            "release-v1/",
            "--no-progress",
        ],
    )
    assert download_result.exit_code == 0, download_result.output
    assert "downloaded 2 file(s)" in download_result.output
    assert (dest / "nested" / "a.bin").read_bytes() == b"AAA"
    assert (dest / "top.bin").read_bytes() == b"TOP"


def test_download_dir_without_prefix_downloads_whole_project(
    runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path
) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.bin").write_bytes(b"A")
    cli_storage.upload_dir(
        bucket=NimbusBucketType.DATASETS,
        project=PROJECT,
        local_dir=src,
        key_prefix="prefix/",
        show_progress=False,
    )

    dest = tmp_path / "dest"
    result = runner.invoke(
        app,
        ["download-dir", "datasets", PROJECT, str(dest), "--no-progress"],
    )
    assert result.exit_code == 0, result.output
    assert (dest / "prefix" / "a.bin").read_bytes() == b"A"


def test_purge_test_bucket_with_yes_flag(runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    for key in ("a.bin", "nested/b.bin", "c.bin"):
        cli_storage.upload_file(
            bucket=NimbusBucketType.TEST,
            project="smoke",
            key=key,
            local_path=src,
            show_progress=False,
        )

    result = runner.invoke(app, ["purge-test-bucket", "--yes"])

    assert result.exit_code == 0, result.output
    assert "deleted 3 object(s)" in result.output
    assert list(cli_storage.list_keys(bucket=NimbusBucketType.TEST, project="smoke")) == []


def test_purge_test_bucket_confirmation_decline(
    runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path
) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    cli_storage.upload_file(
        bucket=NimbusBucketType.TEST,
        project="smoke",
        key="keep.bin",
        local_path=src,
        show_progress=False,
    )

    result = runner.invoke(app, ["purge-test-bucket"], input="n\n")

    assert result.exit_code == 1
    assert "aborted" in result.output
    assert cli_storage.exists(bucket=NimbusBucketType.TEST, project="smoke", key="keep.bin")


def test_purge_test_bucket_confirmation_accept(
    runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path
) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    cli_storage.upload_file(
        bucket=NimbusBucketType.TEST,
        project="smoke",
        key="doomed.bin",
        local_path=src,
        show_progress=False,
    )

    result = runner.invoke(app, ["purge-test-bucket"], input="y\n")

    assert result.exit_code == 0, result.output
    assert "deleted 1 object(s)" in result.output
    assert not cli_storage.exists(bucket=NimbusBucketType.TEST, project="smoke", key="doomed.bin")


def test_purge_test_bucket_does_not_touch_other_buckets(
    runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path
) -> None:
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    cli_storage.upload_file(
        bucket=NimbusBucketType.CHECKPOINTS,
        project=PROJECT,
        key="protected.bin",
        local_path=src,
        show_progress=False,
    )
    cli_storage.upload_file(
        bucket=NimbusBucketType.TEST,
        project="smoke",
        key="doomed.bin",
        local_path=src,
        show_progress=False,
    )

    result = runner.invoke(app, ["purge-test-bucket", "--yes"])

    assert result.exit_code == 0
    assert cli_storage.exists(bucket=NimbusBucketType.CHECKPOINTS, project=PROJECT, key="protected.bin")


def test_os_environ_does_not_leak_secret_into_output(
    runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path
) -> None:
    secret = os.environ["R2_SECRET_ACCESS_KEY"]
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    result = runner.invoke(app, ["upload", "datasets", PROJECT, "a.bin", str(src), "--no-progress"])
    assert result.exit_code == 0
    assert secret not in result.output
