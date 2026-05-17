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

    The first three are intentionally generic ML-data categories. TEST is
    reserved for integration testing and is the only bucket the test suite
    is ever permitted to write to or read from.
    """

    RAW_DATA = "raw-data"
    DATASETS = "datasets"
    CHECKPOINTS = "checkpoints"
    TEST = "test"
