"""Ideal-customer rule, labels, and difficulty."""

from costwise.domain.company import CompanyRecord
from costwise.domain.frozen import FrozenModel
from costwise.domain.task import Difficulty

_ZERO = 0
_PERCENT = 100.0


class IcpRule(FrozenModel):
    """Thresholds that decide whether a company fits."""

    min_employees: int
    max_employees: int
    allowed_stages: frozenset[str]
    min_engineering_open_roles: int
    near_threshold_pct: float


def label_company(record: CompanyRecord, rule: IcpRule) -> bool:
    """Return whether the company matches every ICP threshold."""
    employees = record.employee_count
    stage = record.funding_stage
    roles = record.engineering_open_roles
    if employees is None or stage is None or roles is None:
        return False
    in_headcount = rule.min_employees <= employees <= rule.max_employees
    return (
        in_headcount and stage in rule.allowed_stages and roles >= rule.min_engineering_open_roles
    )


def classify_difficulty(record: CompanyRecord, rule: IcpRule) -> Difficulty:
    """Return HARD when an ICP input is missing or a value sits near a threshold."""
    if missing_field_count(record, rule) or is_near_threshold(record, rule):
        return Difficulty.HARD
    return Difficulty.EASY


def missing_field_count(record: CompanyRecord, rule: IcpRule) -> int:
    """Count missing employee, funding-stage, and engineering-role inputs for this rule."""
    del rule
    values = (record.employee_count, record.funding_stage, record.engineering_open_roles)
    return sum(value is None for value in values)


def is_near_threshold(record: CompanyRecord, rule: IcpRule) -> bool:
    """Return whether a present numeric ICP input is within the near-threshold band."""
    percent = rule.near_threshold_pct
    near_employee = _employee_near(record.employee_count, rule, percent)
    near_roles = _value_near(
        record.engineering_open_roles, rule.min_engineering_open_roles, percent
    )
    return near_employee or near_roles


def _employee_near(employees: int | None, rule: IcpRule, percent: float) -> bool:
    """Return whether headcount is near the minimum or maximum."""
    if employees is None:
        return False
    near_min = _within_percent(employees, rule.min_employees, percent)
    near_max = _within_percent(employees, rule.max_employees, percent)
    return near_min or near_max


def _value_near(value: int | None, threshold: int, percent: float) -> bool:
    """Return whether a present value is inside the threshold window."""
    if value is None:
        return False
    return _within_percent(value, threshold, percent)


def _within_percent(value: int, threshold: int, percent: float) -> bool:
    """Return whether value is within percent of threshold, inclusive."""
    if threshold == _ZERO:
        return value == _ZERO
    window = abs(threshold) * (percent / _PERCENT)
    return abs(value - threshold) <= window
