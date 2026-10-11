"""Clock that returns one injected timestamp."""


class FixedClock:
    """Return the nanosecond timestamp supplied at construction."""

    def __init__(self, now_ns: int) -> None:
        """Store the timestamp returned by every call."""
        self._now_ns = now_ns

    def now_ns(self) -> int:
        """Return the injected timestamp."""
        return self._now_ns
