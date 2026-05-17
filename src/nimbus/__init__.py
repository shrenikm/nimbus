"""
nimbus: a small, project-agnostic Python package for storing files on
S3-compatible object storage.

Public API:

    from nimbus import BucketType, CloudConfig, CloudStorage, NimbusError

Everything else is an internal detail and may change between releases.
"""

from __future__ import annotations

from nimbus.bucket import BucketType
from nimbus.config import CloudConfig
from nimbus.exceptions import (
    NimbusConfigError,
    NimbusError,
    NimbusObjectNotFoundError,
    NimbusStorageError,
    NimbusValidationError,
)
from nimbus.storage import CloudStorage

__version__ = "0.1.0"

__all__ = [
    "BucketType",
    "CloudConfig",
    "CloudStorage",
    "NimbusConfigError",
    "NimbusError",
    "NimbusObjectNotFoundError",
    "NimbusStorageError",
    "NimbusValidationError",
    "__version__",
]
