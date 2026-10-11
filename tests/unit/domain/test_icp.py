"""ICP labels, missing fields, and difficulty."""

import pytest

from costwise.domain.icp import (
    classify_difficulty,
    is_near_threshold,
    label_company,
    missing_field_count,
)
from costwise.domain.task import Difficulty
from tests.unit.domain.builders import make_company, make_rule

_EASY = Difficulty.EASY
_HARD = Difficulty.HARD


@pytest.mark.parametrize(
    ("employees", "stage", "roles", "fit"),
    [
        (200, "series_a", 20, True),
        (50, "series_a", 20, True),
        (1000, "series_b", 20, True),
        (49, "series_a", 20, False),
        (1001, "series_a", 20, False),
        (200, "seed", 20, False),
        (200, "Series A", 20, False),
        (200, "series_a", 9, False),
        (None, "series_a", 20, False),
        (200, None, 20, False),
        (200, "series_a", None, False),
    ],
)
def test_label_company(
    employees: int | None,
    stage: str | None,
    roles: int | None,
    fit: bool,
) -> None:
    """A company fits only when every ICP input is present and inside the rule."""
    record = make_company(employees, stage, roles)
    assert label_company(record, make_rule()) is fit


@pytest.mark.parametrize(
    ("employees", "stage", "roles", "missing"),
    [
        (200, "series_a", 20, 0),
        (None, "series_a", 20, 1),
        (None, None, 20, 2),
        (None, None, None, 3),
    ],
)
def test_missing_field_count(
    employees: int | None,
    stage: str | None,
    roles: int | None,
    missing: int,
) -> None:
    """Missing count covers employee count, funding stage, and engineering roles."""
    record = make_company(employees, stage, roles)
    assert missing_field_count(record, make_rule()) == missing


@pytest.mark.parametrize(
    ("employees", "roles", "near"),
    [
        (200, 20, False),
        (50, 20, True),
        (55, 20, True),
        (56, 20, False),
        (45, 20, True),
        (44, 20, False),
        (1000, 20, True),
        (900, 20, True),
        (899, 20, False),
        (200, 10, True),
        (200, 11, True),
        (200, 12, False),
        (None, 20, False),
        (200, None, False),
        (None, None, False),
    ],
)
def test_is_near_threshold(employees: int | None, roles: int | None, near: bool) -> None:
    """Numeric inputs within 10 percent of a threshold are near, inclusive."""
    record = make_company(employees, "series_a", roles)
    assert is_near_threshold(record, make_rule()) is near


def test_zero_threshold_is_near_only_at_zero() -> None:
    """A zero threshold has no percentage window, so only zero itself is near."""
    rule = make_rule().model_copy(update={"min_engineering_open_roles": 0})
    assert is_near_threshold(make_company(200, "series_a", 0), rule) is True
    assert is_near_threshold(make_company(200, "series_a", 3), rule) is False


@pytest.mark.parametrize(
    ("employees", "stage", "roles", "difficulty"),
    [
        (200, "series_a", 20, _EASY),
        (200, "seed", 20, _EASY),
        (40, "series_a", 20, _EASY),
        (None, "series_a", 20, _HARD),
        (200, None, 20, _HARD),
        (200, "series_a", None, _HARD),
        (50, "series_a", 20, _HARD),
        (55, "series_a", 20, _HARD),
        (56, "series_a", 20, _EASY),
        (200, "series_a", 10, _HARD),
        (200, "series_a", 12, _EASY),
    ],
)
def test_classify_difficulty(
    employees: int | None,
    stage: str | None,
    roles: int | None,
    difficulty: Difficulty,
) -> None:
    """Clear fits and clear misses are easy. Missing or borderline inputs are hard."""
    record = make_company(employees, stage, roles)
    assert classify_difficulty(record, make_rule()) is difficulty
