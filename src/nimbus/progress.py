"""
tqdm-backed progress callback for boto3 transfer operations.

boto3's upload/download_file accept a Callback(bytes_transferred) function
that gets invoked after each chunk. NimbusProgressCallback wraps a tqdm bar so
the user gets a live progress meter during long transfers.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self

from tqdm import tqdm


class NimbusProgressCallback:
    """
    Callable that updates a tqdm progress bar from boto3's per-chunk callback.

    Use as a context manager so the bar is always closed cleanly.
    """

    def __init__(self, *, total_bytes: int, description: str) -> None:
        self._bar = tqdm(
            total=total_bytes,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=description,
            leave=False,
            dynamic_ncols=True,
        )

    def __call__(self, bytes_transferred: int) -> None:
        self._bar.update(bytes_transferred)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._bar.close()

    def close(self) -> None:
        self._bar.close()
