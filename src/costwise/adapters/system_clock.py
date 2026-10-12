"""Clock backed by the operating system."""

import time


class SystemClock:
    """Return wall-clock time since the Unix epoch in nanoseconds."""

    def now_ns(self) -> int:
        """Return time.time_ns()."""
        return time.time_ns()
