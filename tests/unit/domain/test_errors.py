"""Error type relationships."""

import pytest

from costwise.domain.errors import (
    BudgetExceededError,
    ConfigError,
    CostwiseError,
    DataSourceError,
    LLMError,
    ParseError,
    RunnerError,
)


@pytest.mark.parametrize(
    "error_type",
    [
        ConfigError,
        BudgetExceededError,
        DataSourceError,
        LLMError,
        RunnerError,
        ParseError,
    ],
)
def test_errors_extend_costwise_error(error_type: type[CostwiseError]) -> None:
    """Every typed error can be caught as CostwiseError."""
    with pytest.raises(CostwiseError):
        raise error_type("failed")
