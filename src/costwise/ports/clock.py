"""Port for injected time."""

from typing import Protocol


class Clock(Protocol):
    """Supplies the current time in nanoseconds."""

    def now_ns(self) -> int:
        """Return the current monotonic-or-wall time in nanoseconds."""
        ...
