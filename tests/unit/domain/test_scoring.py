"""Success checks for qualification answers."""

import pytest

from costwise.domain.scoring import is_success
from costwise.domain.task import QualificationAnswer


def _answer(fit: bool) -> QualificationAnswer:
    """Build an answer with the given fit bit."""
    return QualificationAnswer(
        icp_fit=fit, reasons=("because",), headcount_band="51-200", stage="series_a"
    )


@pytest.mark.parametrize(
    ("answer", "expected_fit", "success"),
    [
        (None, True, False),
        (None, False, False),
        (_answer(True), True, True),
        (_answer(False), False, True),
        (_answer(True), False, False),
        (_answer(False), True, False),
    ],
)
def test_is_success(answer: QualificationAnswer | None, expected_fit: bool, success: bool) -> None:
    """Success requires a parsed answer whose fit matches the label."""
    assert is_success(answer, expected_fit) is success
