"""Typed errors raised by costwise."""


class CostwiseError(Exception):
    """Base error for every costwise failure."""


class ConfigError(CostwiseError):
    """Raised when configuration or a proposal is invalid."""


class BudgetExceededError(CostwiseError):
    """Raised when a run would pass the budget stop line."""


class DataSourceError(CostwiseError):
    """Raised when company data cannot be fetched."""


class LLMError(CostwiseError):
    """Raised when a model call fails."""


class TransientLLMError(LLMError):
    """Raised when a model call hit a rate limit, server error, or timeout and may be retried."""


class RunnerError(CostwiseError):
    """Raised when a task runner fails."""


class ParseError(CostwiseError):
    """Raised when a model response is not a valid qualification answer."""
