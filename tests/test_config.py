from __future__ import annotations

import attrs.exceptions
import pytest

from nimbus.bucket import NimbusBucketType
from nimbus.config import (
    DEFAULT_BUCKET_PREFIX,
    DEFAULT_REGION,
    NimbusCloudConfig,
)
from nimbus.exceptions import NimbusConfigError


class TestNimbusCloudConfigConstruction:
    def test_minimal_construction(self) -> None:
        config = NimbusCloudConfig(
            endpoint_url="https://example.com",
            access_key_id="ak",
            secret_access_key="sk",
        )
        assert config.endpoint_url == "https://example.com"
        assert config.access_key_id == "ak"
        assert config.secret_access_key == "sk"
        assert config.bucket_prefix == DEFAULT_BUCKET_PREFIX
        assert config.region == DEFAULT_REGION
        assert dict(config.bucket_overrides) == {}

    def test_repr_does_not_leak_secret(self) -> None:
        config = NimbusCloudConfig(
            endpoint_url="https://example.com",
            access_key_id="ak",
            secret_access_key="super-secret-do-not-leak",
        )
        assert "super-secret-do-not-leak" not in repr(config)

    @pytest.mark.parametrize("field", ["endpoint_url", "access_key_id", "secret_access_key"])
    def test_rejects_empty_required_field(self, field: str) -> None:
        kwargs = {
            "endpoint_url": "https://example.com",
            "access_key_id": "ak",
            "secret_access_key": "sk",
        }
        kwargs[field] = ""
        with pytest.raises(NimbusConfigError):
            NimbusCloudConfig(**kwargs)

    def test_rejects_empty_bucket_prefix(self) -> None:
        with pytest.raises(NimbusConfigError):
            NimbusCloudConfig(
                endpoint_url="https://example.com",
                access_key_id="ak",
                secret_access_key="sk",
                bucket_prefix="",
            )

    def test_is_frozen(self) -> None:
        config = NimbusCloudConfig(
            endpoint_url="https://example.com",
            access_key_id="ak",
            secret_access_key="sk",
        )
        with pytest.raises(attrs.exceptions.FrozenInstanceError):
            config.bucket_prefix = "other"  # type: ignore[misc]


class TestBucketNameResolution:
    def test_prefix_based_default(self) -> None:
        config = NimbusCloudConfig(
            endpoint_url="https://example.com",
            access_key_id="ak",
            secret_access_key="sk",
            bucket_prefix="my-prefix",
        )
        assert config.bucket_name(NimbusBucketType.RAW_DATA) == "my-prefix-raw-data"
        assert config.bucket_name(NimbusBucketType.DATASETS) == "my-prefix-datasets"
        assert config.bucket_name(NimbusBucketType.CHECKPOINTS) == "my-prefix-checkpoints"

    def test_explicit_overrides_take_precedence(self) -> None:
        config = NimbusCloudConfig(
            endpoint_url="https://example.com",
            access_key_id="ak",
            secret_access_key="sk",
            bucket_prefix="my-prefix",
            bucket_overrides={NimbusBucketType.CHECKPOINTS: "custom-ckpt-bucket"},
        )
        assert config.bucket_name(NimbusBucketType.CHECKPOINTS) == "custom-ckpt-bucket"
        assert config.bucket_name(NimbusBucketType.DATASETS) == "my-prefix-datasets"

    def test_overrides_accept_string_keys(self) -> None:
        config = NimbusCloudConfig(
            endpoint_url="https://example.com",
            access_key_id="ak",
            secret_access_key="sk",
            bucket_overrides={"checkpoints": "custom-ckpt-bucket"},
        )
        assert config.bucket_name(NimbusBucketType.CHECKPOINTS) == "custom-ckpt-bucket"

    def test_string_bucket_type_resolved(self) -> None:
        config = NimbusCloudConfig(
            endpoint_url="https://example.com",
            access_key_id="ak",
            secret_access_key="sk",
            bucket_prefix="my-prefix",
        )
        assert config.bucket_name("datasets") == "my-prefix-datasets"

    def test_unknown_bucket_type_raises(self) -> None:
        config = NimbusCloudConfig(
            endpoint_url="https://example.com",
            access_key_id="ak",
            secret_access_key="sk",
        )
        with pytest.raises(NimbusConfigError):
            config.bucket_name("nope")


class TestFromEnv:
    def _setup_required(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("R2_ENDPOINT_URL", "https://acc.r2.cloudflarestorage.com")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk")

    def test_reads_required_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_required(monkeypatch)
        config = NimbusCloudConfig.from_env()
        assert config.endpoint_url == "https://acc.r2.cloudflarestorage.com"
        assert config.access_key_id == "ak"
        assert config.secret_access_key == "sk"
        assert config.bucket_prefix == DEFAULT_BUCKET_PREFIX

    def test_builds_endpoint_from_account_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("R2_ACCOUNT_ID", "my-acc")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk")
        config = NimbusCloudConfig.from_env()
        assert config.endpoint_url == "https://my-acc.r2.cloudflarestorage.com"

    def test_endpoint_url_wins_over_account_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("R2_ENDPOINT_URL", "https://explicit.example.com")
        monkeypatch.setenv("R2_ACCOUNT_ID", "ignored-account-id")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk")
        config = NimbusCloudConfig.from_env()
        assert config.endpoint_url == "https://explicit.example.com"

    def test_per_type_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._setup_required(monkeypatch)
        monkeypatch.setenv("NIMBUS_BUCKET_CHECKPOINTS", "my-ckpts")
        monkeypatch.setenv("NIMBUS_BUCKET_DATASETS", "my-datasets")
        config = NimbusCloudConfig.from_env()
        assert config.bucket_name(NimbusBucketType.CHECKPOINTS) == "my-ckpts"
        assert config.bucket_name(NimbusBucketType.DATASETS) == "my-datasets"
        assert config.bucket_name(NimbusBucketType.RAW_DATA).endswith("-raw-data")

    def test_missing_credentials_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("R2_ENDPOINT_URL", "https://example.com")
        with pytest.raises(NimbusConfigError):
            NimbusCloudConfig.from_env()

    def test_missing_endpoint_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "ak")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sk")
        with pytest.raises(NimbusConfigError):
            NimbusCloudConfig.from_env()
