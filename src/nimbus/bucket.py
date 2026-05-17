"""
Bucket-type taxonomy for nimbus.

NimbusBucketType values are plain strings (StrEnum) so they can be substituted
directly into bucket names. The string forms are DNS-compliant (lowercase,
hyphen-separated) and therefore valid as bucket-name suffixes.
"""

from __future__ import annotations

from enum import StrEnum


class NimbusBucketType(StrEnum):
    """
    Categories of data nimbus knows how to address.

    These are intentionally generic ML-data categories. Downstream users
    with different category names may pass raw strings to the API; nothing
    in nimbus assumes the taxonomy is exhaustive.
    """

    RAW_DATA = "raw-data"
    DATASETS = "datasets"
    CHECKPOINTS = "checkpoints"
