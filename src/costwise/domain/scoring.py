"""Success rule for a qualification answer."""

from costwise.domain.task import QualificationAnswer


def is_success(answer: QualificationAnswer | None, expected_fit: bool) -> bool:
    """Return whether a parsed answer matches the expected ICP fit."""
    if answer is None:
        return False
    return answer.icp_fit is expected_fit
