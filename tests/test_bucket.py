from __future__ import annotations

from nimbus.bucket import BucketType


def test_bucket_type_values_are_dns_compliant() -> None:
    for bucket_type in BucketType:
        value = bucket_type.value
        assert value == value.lower()
        assert "_" not in value
        assert all(part for part in value.split("-"))


def test_bucket_type_is_str_subclass() -> None:
    assert isinstance(BucketType.CHECKPOINTS, str)
    assert BucketType.CHECKPOINTS == "checkpoints"


def test_bucket_type_round_trip_from_value() -> None:
    for bucket_type in BucketType:
        assert BucketType(bucket_type.value) is bucket_type


def test_bucket_type_membership_set() -> None:
    assert {b.value for b in BucketType} == {"raw-data", "datasets", "checkpoints"}
