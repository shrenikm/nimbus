"""
Thin factory that turns a NimbusCloudConfig into a configured boto3 S3 client.

The R2 (and most non-AWS S3-compatible) endpoints expect virtual-hosted
addressing to be off; we set signature_version=s3v4 to satisfy R2's
requirements.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import boto3
from botocore.config import Config as BotoConfig

from nimbus.config import NimbusCloudConfig

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
else:
    S3Client = Any

DEFAULT_SIGNATURE_VERSION = "s3v4"
DEFAULT_ADDRESSING_STYLE = "path"


def build_s3_client(config: NimbusCloudConfig) -> S3Client:
    """
    Construct a boto3 S3 client wired up for the configured endpoint.
    """
    boto_config = BotoConfig(
        signature_version=DEFAULT_SIGNATURE_VERSION,
        s3={"addressing_style": DEFAULT_ADDRESSING_STYLE},
        retries={"max_attempts": 5, "mode": "standard"},
    )
    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region,
        config=boto_config,
    )
