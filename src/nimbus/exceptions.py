"""
Exception hierarchy for the nimbus package.

All nimbus-raised errors inherit from NimbusError so callers can catch the
whole family with a single except clause.
"""

from __future__ import annotations


class NimbusError(Exception):
    """
    Base class for every error raised by nimbus.
    """


class NimbusConfigError(NimbusError):
    """
    Raised when CloudConfig cannot be constructed (missing env vars,
    invalid values, etc.).
    """


class NimbusValidationError(NimbusError):
    """
    Raised when a caller passes an invalid argument (bad project name,
    empty key, unknown bucket type, etc.).
    """


class NimbusStorageError(NimbusError):
    """
    Raised when an object-storage operation fails for reasons other than
    the object simply not existing.
    """


class NimbusObjectNotFoundError(NimbusStorageError):
    """
    Raised when an object that was expected to exist is missing.
    """
