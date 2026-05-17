"""
Configuration for nimbus.

NimbusCloudConfig is a frozen attrs dataclass that holds everything the storage
client needs: endpoint, credentials, and how to resolve bucket names. The
from_env() constructor reads a small, documented set of environment
variables (and a .env file if present) so that calling code can simply do:

    config = NimbusCloudConfig.from_env()
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Self

import attrs
from dotenv import load_dotenv

from nimbus.bucket import NimbusBucketType
from nimbus.exceptions import NimbusConfigError

DEFAULT_BUCKET_PREFIX = "nimbus"
DEFAULT_REGION = "auto"

ENV_ENDPOINT_URL = "R2_ENDPOINT_URL"
ENV_ACCOUNT_ID = "R2_ACCOUNT_ID"
ENV_ACCESS_KEY_ID = "R2_ACCESS_KEY_ID"
ENV_SECRET_ACCESS_KEY = "R2_SECRET_ACCESS_KEY"
ENV_BUCKET_PREFIX = "NIMBUS_BUCKET_PREFIX"
ENV_BUCKET_OVERRIDE_PREFIX = "NIMBUS_BUCKET_"


def _bucket_overrides_converter(
    value: Mapping[NimbusBucketType | str, str] | None,
) -> Mapping[NimbusBucketType, str]:
    """
    Normalize a user-supplied overrides mapping so keys are always NimbusBucketType
    members and the resulting mapping is immutable.
    """
    if value is None:
        return {}
    normalized: dict[NimbusBucketType, str] = {}
    for raw_key, raw_value in value.items():
        bucket_type = (
            raw_key if isinstance(raw_key, NimbusBucketType) else NimbusBucketType(raw_key)
        )
        if not isinstance(raw_value, str) or not raw_value:
            raise NimbusConfigError(
                f"bucket override for {bucket_type.value!r} must be a non-empty string"
            )
        normalized[bucket_type] = raw_value
    return normalized


@attrs.frozen(slots=True, kw_only=True)
class NimbusCloudConfig:
    """
    All settings nimbus needs to talk to an S3-compatible object store.

    bucket_prefix is combined with each NimbusBucketType value to form the default
    bucket name (e.g. "nimbus" + "checkpoints" -> "nimbus-checkpoints").
    bucket_overrides take precedence over the prefix-based name.
    """

    endpoint_url: str = attrs.field(validator=attrs.validators.instance_of(str))
    access_key_id: str = attrs.field(validator=attrs.validators.instance_of(str))
    secret_access_key: str = attrs.field(validator=attrs.validators.instance_of(str), repr=False)
    bucket_prefix: str = attrs.field(
        default=DEFAULT_BUCKET_PREFIX, validator=attrs.validators.instance_of(str)
    )
    bucket_overrides: Mapping[NimbusBucketType, str] = attrs.field(
        factory=dict, converter=_bucket_overrides_converter
    )
    region: str = attrs.field(default=DEFAULT_REGION, validator=attrs.validators.instance_of(str))

    def __attrs_post_init__(self) -> None:
        if not self.endpoint_url:
            raise NimbusConfigError("endpoint_url must not be empty")
        if not self.access_key_id:
            raise NimbusConfigError("access_key_id must not be empty")
        if not self.secret_access_key:
            raise NimbusConfigError("secret_access_key must not be empty")
        if not self.bucket_prefix:
            raise NimbusConfigError("bucket_prefix must not be empty")

    @classmethod
    def from_env(cls, *, dotenv_path: str | os.PathLike[str] | None = None) -> Self:
        """
        Build a NimbusCloudConfig from environment variables, loading .env first if
        one is present in the working directory (or at dotenv_path).
        """
        load_dotenv(dotenv_path=dotenv_path, override=False)

        endpoint_url = os.environ.get(ENV_ENDPOINT_URL, "").strip()
        if not endpoint_url:
            account_id = os.environ.get(ENV_ACCOUNT_ID, "").strip()
            if account_id:
                endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        if not endpoint_url:
            raise NimbusConfigError(
                f"missing endpoint configuration: set {ENV_ENDPOINT_URL} or {ENV_ACCOUNT_ID}"
            )

        access_key_id = os.environ.get(ENV_ACCESS_KEY_ID, "").strip()
        if not access_key_id:
            raise NimbusConfigError(f"missing environment variable: {ENV_ACCESS_KEY_ID}")

        secret_access_key = os.environ.get(ENV_SECRET_ACCESS_KEY, "")
        if not secret_access_key:
            raise NimbusConfigError(f"missing environment variable: {ENV_SECRET_ACCESS_KEY}")

        bucket_prefix = os.environ.get(ENV_BUCKET_PREFIX, "").strip() or DEFAULT_BUCKET_PREFIX

        overrides: dict[NimbusBucketType, str] = {}
        for bucket_type in NimbusBucketType:
            env_name = ENV_BUCKET_OVERRIDE_PREFIX + bucket_type.name
            override_value = os.environ.get(env_name, "").strip()
            if override_value:
                overrides[bucket_type] = override_value

        return cls(
            endpoint_url=endpoint_url,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            bucket_prefix=bucket_prefix,
            bucket_overrides=overrides,
        )

    def bucket_name(self, bucket_type: NimbusBucketType | str) -> str:
        """
        Resolve the underlying bucket name for a given category.
        """
        bucket_type = self._coerce_bucket_type(bucket_type)
        override = self.bucket_overrides.get(bucket_type)
        if override is not None:
            return override
        return f"{self.bucket_prefix}-{bucket_type.value}"

    @staticmethod
    def _coerce_bucket_type(bucket_type: NimbusBucketType | str) -> NimbusBucketType:
        if isinstance(bucket_type, NimbusBucketType):
            return bucket_type
        try:
            return NimbusBucketType(bucket_type)
        except ValueError as exc:
            raise NimbusConfigError(f"unknown bucket type: {bucket_type!r}") from exc
