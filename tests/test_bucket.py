from __future__ import annotations

from nimbus.bucket import NimbusBucketType


def test_bucket_type_values_are_dns_compliant() -> None:
    for bucket_type in NimbusBucketType:
        value = bucket_type.value
        assert value == value.lower()
        assert "_" not in value
        assert all(part for part in value.split("-"))


def test_bucket_type_is_str_subclass() -> None:
    assert isinstance(NimbusBucketType.CHECKPOINTS, str)
    assert NimbusBucketType.CHECKPOINTS == "checkpoints"


def test_bucket_type_round_trip_from_value() -> None:
    for bucket_type in NimbusBucketType:
        assert NimbusBucketType(bucket_type.value) is bucket_type


def test_bucket_type_membership_set() -> None:
    assert {b.value for b in NimbusBucketType} == {"raw-data", "datasets", "checkpoints", "test"}
