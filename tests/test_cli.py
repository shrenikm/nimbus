from __future__ import annotations

import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from nimbus.bucket import NimbusBucketType
from nimbus.cli import main
from nimbus.config import NimbusCloudConfig
from nimbus.storage import NimbusCloudStorage
from tests.conftest import TEST_BUCKET_PREFIX, TEST_REGION

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
    monkeypatch.setenv("NIMBUS_BUCKET_PREFIX", TEST_BUCKET_PREFIX)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_storage(mocked_s3: None, cli_env: None) -> NimbusCloudStorage:
    config = NimbusCloudConfig(
        endpoint_url="https://s3.amazonaws.com",
        access_key_id="testing",
        secret_access_key="testing",
        bucket_prefix=TEST_BUCKET_PREFIX,
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
        main,
        [
            "upload",
            "checkpoints",
            PROJECT,
            "run/a.bin",
            str(src),
            "--no-progress",
        ],
    )
    assert upload_result.exit_code == 0, upload_result.output
    assert f"{PROJECT}/run/a.bin" in upload_result.output

    ls_result = runner.invoke(main, ["ls", "checkpoints", PROJECT])
    assert ls_result.exit_code == 0
    assert "run/a.bin" in ls_result.output

    dest = tmp_path / "out.bin"
    download_result = runner.invoke(
        main,
        [
            "download",
            "checkpoints",
            PROJECT,
            "run/a.bin",
            str(dest),
            "--no-progress",
        ],
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
    yes = runner.invoke(main, ["exists", "checkpoints", PROJECT, "present.bin"])
    assert yes.exit_code == 0
    assert "yes" in yes.output

    no = runner.invoke(main, ["exists", "checkpoints", PROJECT, "absent.bin"])
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
    result = runner.invoke(main, ["rm", "checkpoints", PROJECT, "doomed.bin"])
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
    result = runner.invoke(
        main,
        ["presign", "datasets", PROJECT, "a.bin", "--expires", "120"],
    )
    assert result.exit_code == 0
    assert result.output.strip().startswith("http")


def test_bucket_type_choice_validation(runner: CliRunner) -> None:
    result = runner.invoke(main, ["ls", "not-a-bucket-type", PROJECT])
    assert result.exit_code != 0
    assert "Invalid value" in result.output or "Usage" in result.output


def test_help_lists_all_commands(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    for command in ("upload", "download", "ls", "exists", "rm", "presign"):
        assert command in result.output


def test_os_environ_does_not_leak_secret_into_output(
    runner: CliRunner, cli_storage: NimbusCloudStorage, tmp_path: Path
) -> None:
    secret = os.environ["R2_SECRET_ACCESS_KEY"]
    src = tmp_path / "src.bin"
    src.write_bytes(b"x")
    result = runner.invoke(
        main,
        ["upload", "datasets", PROJECT, "a.bin", str(src), "--no-progress"],
    )
    assert result.exit_code == 0
    assert secret not in result.output
