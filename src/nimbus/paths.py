"""
Helpers for assembling and validating object-storage keys.

The convention is `{project}/{key}` where project is a top-level prefix
chosen by the caller and key is the rest of the object path inside that
project. nimbus never imposes structure inside the key.
"""

from __future__ import annotations

import re

from nimbus.exceptions import NimbusValidationError

PROJECT_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")

KEY_FORBIDDEN_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


def validate_project_name(project: str) -> str:
    """
    Validate a project namespace and return it unchanged on success.

    Rules: lowercase letters, digits, dot, underscore, hyphen; must start
    with a letter or digit; 1-63 characters. These rules match common
    DNS-style bucket naming so a project name can also be used in the
    bucket prefix if a downstream caller wants that.
    """
    if not isinstance(project, str):
        raise NimbusValidationError(f"project name must be a string, got {type(project).__name__}")
    if not project:
        raise NimbusValidationError("project name must not be empty")
    if not PROJECT_NAME_PATTERN.fullmatch(project):
        raise NimbusValidationError(f"invalid project name {project!r}: must match {PROJECT_NAME_PATTERN.pattern}")
    return project


def validate_key(key: str) -> str:
    """
    Validate the per-object key portion (everything after the project prefix).

    Disallows empty strings, leading slashes, and control characters.
    """
    if not isinstance(key, str):
        raise NimbusValidationError(f"key must be a string, got {type(key).__name__}")
    if not key:
        raise NimbusValidationError("key must not be empty")
    if key.startswith("/"):
        raise NimbusValidationError(f"key must not start with '/': {key!r}")
    if KEY_FORBIDDEN_PATTERN.search(key):
        raise NimbusValidationError(f"key contains control characters: {key!r}")
    return key


def join_key(project: str, key: str) -> str:
    """
    Compose the final S3 object key from a project namespace and a per-object key.
    """
    project = validate_project_name(project)
    key = validate_key(key)
    return f"{project}/{key}"


def normalize_prefix(prefix: str) -> str:
    """
    Normalize a key prefix used for listing: empty string is allowed (lists
    everything under the project) and leading slashes are stripped.
    """
    if not isinstance(prefix, str):
        raise NimbusValidationError(f"prefix must be a string, got {type(prefix).__name__}")
    if KEY_FORBIDDEN_PATTERN.search(prefix):
        raise NimbusValidationError(f"prefix contains control characters: {prefix!r}")
    return prefix.lstrip("/")
