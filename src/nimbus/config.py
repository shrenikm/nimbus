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


@attrs.frozen(slots=True, kw_only=True)
class NimbusCloudConfig:
    """
    All settings nimbus needs to talk to an S3-compatible object store.

    bucket_prefix is combined with each NimbusBucketType value to form the
    final bucket name (e.g. "nimbus" + "checkpoints" -> "nimbus-checkpoints").
    """

    endpoint_url: str = attrs.field(validator=attrs.validators.instance_of(str))
    access_key_id: str = attrs.field(validator=attrs.validators.instance_of(str))
    secret_access_key: str = attrs.field(validator=attrs.validators.instance_of(str), repr=False)
    bucket_prefix: str = attrs.field(default=DEFAULT_BUCKET_PREFIX, validator=attrs.validators.instance_of(str))
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
            raise NimbusConfigError(f"missing endpoint configuration: set {ENV_ENDPOINT_URL} or {ENV_ACCOUNT_ID}")

        access_key_id = os.environ.get(ENV_ACCESS_KEY_ID, "").strip()
        if not access_key_id:
            raise NimbusConfigError(f"missing environment variable: {ENV_ACCESS_KEY_ID}")

        secret_access_key = os.environ.get(ENV_SECRET_ACCESS_KEY, "")
        if not secret_access_key:
            raise NimbusConfigError(f"missing environment variable: {ENV_SECRET_ACCESS_KEY}")

        return cls(
            endpoint_url=endpoint_url,
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
        )

    def bucket_name(self, bucket_type: NimbusBucketType | str) -> str:
        """
        Resolve the underlying bucket name for a given category.
        """
        bucket_type = self._coerce_bucket_type(bucket_type)
        return f"{self.bucket_prefix}-{bucket_type.value}"

    @staticmethod
    def _coerce_bucket_type(bucket_type: NimbusBucketType | str) -> NimbusBucketType:
        if isinstance(bucket_type, NimbusBucketType):
            return bucket_type
        try:
            return NimbusBucketType(bucket_type)
        except ValueError as exc:
            raise NimbusConfigError(f"unknown bucket type: {bucket_type!r}") from exc
