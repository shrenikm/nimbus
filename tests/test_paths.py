from __future__ import annotations

import pytest

from nimbus.exceptions import NimbusValidationError
from nimbus.paths import join_key, normalize_prefix, validate_key, validate_project_name


class TestValidateProjectName:
    @pytest.mark.parametrize(
        "project",
        [
            "a",
            "my-project",
            "my_project",
            "project.v1",
            "abc123",
            "a" * 63,
        ],
    )
    def test_accepts_valid_names(self, project: str) -> None:
        assert validate_project_name(project) == project

    @pytest.mark.parametrize(
        "project",
        [
            "",
            "-leading-hyphen",
            "_leading-underscore",
            ".leading-dot",
            "UPPER",
            "with space",
            "with/slash",
            "a" * 64,
            "with$symbol",
        ],
    )
    def test_rejects_invalid_names(self, project: str) -> None:
        with pytest.raises(NimbusValidationError):
            validate_project_name(project)

    def test_rejects_non_string(self) -> None:
        with pytest.raises(NimbusValidationError):
            validate_project_name(42)  # type: ignore[arg-type]


class TestValidateKey:
    @pytest.mark.parametrize(
        "key",
        [
            "file.txt",
            "run-1/best.pth",
            "deeply/nested/path/file.bin",
            "with spaces.txt",
            "weird-but-allowed?.txt",
        ],
    )
    def test_accepts_valid_keys(self, key: str) -> None:
        assert validate_key(key) == key

    def test_rejects_empty(self) -> None:
        with pytest.raises(NimbusValidationError):
            validate_key("")

    def test_rejects_leading_slash(self) -> None:
        with pytest.raises(NimbusValidationError):
            validate_key("/foo/bar")

    def test_rejects_control_chars(self) -> None:
        with pytest.raises(NimbusValidationError):
            validate_key("foo\x00bar")


class TestJoinKey:
    def test_concatenates_with_separator(self) -> None:
        assert join_key("proj", "a/b.txt") == "proj/a/b.txt"

    def test_invalid_project_propagates(self) -> None:
        with pytest.raises(NimbusValidationError):
            join_key("Bad Name", "a")

    def test_invalid_key_propagates(self) -> None:
        with pytest.raises(NimbusValidationError):
            join_key("proj", "")


class TestNormalizePrefix:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("", ""),
            ("foo/", "foo/"),
            ("/foo/", "foo/"),
            ("///foo/", "foo/"),
            ("nested/path", "nested/path"),
        ],
    )
    def test_strips_leading_slashes(self, raw: str, expected: str) -> None:
        assert normalize_prefix(raw) == expected

    def test_rejects_control_chars(self) -> None:
        with pytest.raises(NimbusValidationError):
            normalize_prefix("foo\x01bar")
