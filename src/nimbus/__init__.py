"""
nimbus: a small, project-agnostic Python package for storing files on
S3-compatible object storage.

Public API:

    from nimbus import (
        NimbusBucketType,
        NimbusCloudConfig,
        NimbusCloudStorage,
        NimbusError,
    )

Everything else is an internal detail and may change between releases.
"""

from __future__ import annotations

from nimbus.bucket import NimbusBucketType
from nimbus.config import NimbusCloudConfig
from nimbus.exceptions import (
    NimbusConfigError,
    NimbusError,
    NimbusObjectNotFoundError,
    NimbusStorageError,
    NimbusValidationError,
)
from nimbus.storage import NimbusCloudStorage

__version__ = "0.1.0"

__all__ = [
    "NimbusBucketType",
    "NimbusCloudConfig",
    "NimbusCloudStorage",
    "NimbusConfigError",
    "NimbusError",
    "NimbusObjectNotFoundError",
    "NimbusStorageError",
    "NimbusValidationError",
    "__version__",
]
