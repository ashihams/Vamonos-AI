"""Ground-truth labels and workload settings for fixture companies."""

from pydantic import Field

from costwise.domain.frozen import FrozenModel
from costwise.domain.task import Difficulty, Split


class CompanyLabel(FrozenModel):
    """Expected ICP fit, difficulty, and split for one fixture company."""

    expected_fit: bool
    difficulty: Difficulty
    split: Split


class WorkloadPolicy(FrozenModel):
    """How many requests to build, how often domains repeat, and the held-out size."""

    n_requests: int = Field(ge=1)
    repeat_ratio: float = Field(ge=0.0, lt=1.0)
    heldout_count: int = Field(ge=2)
    seed: int
