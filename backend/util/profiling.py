from __future__ import annotations

import logging
import time
from typing import Any, Optional


def timing_log(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit ``DEBUG timing <event> k=v ...``; no-op if logger is not DEBUG."""
    if not logger.isEnabledFor(logging.DEBUG):
        return
    parts = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.debug("timing %s %s", event, parts)


class Timer:
    """Start with ``Timer(logger, event, **fields).start()``; call ``.log(**extra)`` to emit timing.

    Elapsed time is from ``start()`` until ``log()`` (live), or until ``stop()`` if you call
    ``stop()`` first (frozen duration for later ``log()``). ``log(min_ms=…)`` skips logging
    when below the threshold.
    """

    __slots__ = ("_logger", "_event", "_base", "_t0", "_stop_ms")

    def __init__(self, logger: logging.Logger, event: str, **fields: Any) -> None:
        self._logger = logger
        self._event = event
        self._base = fields
        self._t0: Optional[float] = None
        self._stop_ms: Optional[float] = None

    def start(self) -> Timer:
        if not self._logger.isEnabledFor(logging.DEBUG):
            return self
        self._t0 = time.perf_counter()
        self._stop_ms = None
        return self

    def stop(self) -> float:
        """Return elapsed ms since ``start()`` and freeze that value for a following ``log()``."""
        if not self._logger.isEnabledFor(logging.DEBUG) or self._t0 is None:
            return 0.0
        self._stop_ms = round((time.perf_counter() - self._t0) * 1000, 1)
        self._t0 = None
        return self._stop_ms

    def log(self, *, min_ms: Optional[float] = None, **extra: Any) -> None:
        if not self._logger.isEnabledFor(logging.DEBUG):
            return
        if self._t0 is not None:
            duration_ms = round((time.perf_counter() - self._t0) * 1000, 1)
        elif self._stop_ms is not None:
            duration_ms = self._stop_ms
        else:
            return
        if min_ms is not None and duration_ms < min_ms:
            return
        merged = {**self._base, **extra, "duration_ms": duration_ms}
        timing_log(self._logger, self._event, **merged)
