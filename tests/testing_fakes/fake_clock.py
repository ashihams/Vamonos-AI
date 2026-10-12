"""Clocks that return injected timestamps."""

from collections.abc import Sequence

from costwise.domain.errors import CostwiseError


class FixedClock:
    """Return the nanosecond timestamp supplied at construction."""

    def __init__(self, now_ns: int) -> None:
        """Store the timestamp returned by every call."""
        self._now_ns = now_ns

    def now_ns(self) -> int:
        """Return the injected timestamp."""
        return self._now_ns


class TickingClock:
    """Return scripted timestamps in order, one per call."""

    def __init__(self, ticks_ns: Sequence[int]) -> None:
        """Copy the timestamps to return."""
        self._ticks = list(ticks_ns)

    def now_ns(self) -> int:
        """Return the next timestamp or raise when the script is exhausted."""
        if not self._ticks:
            raise CostwiseError("no scripted time")
        return self._ticks.pop(0)
