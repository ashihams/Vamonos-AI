"""Confirm the package skeleton imports."""

from __future__ import annotations

import importlib

_PACKAGES: tuple[str, ...] = (
    "costwise",
    "costwise.adapters",
    "costwise.adapters.approval",
    "costwise.adapters.data",
    "costwise.adapters.llm",
    "costwise.adapters.runners",
    "costwise.adapters.storage",
    "costwise.adapters.telemetry",
    "costwise.apps",
    "costwise.apps.cli",
    "costwise.apps.lambda_handler",
    "costwise.domain",
    "costwise.ports",
    "costwise.services",
)


def test_scaffold_packages_import() -> None:
    """Every scaffold package imports."""
    for name in _PACKAGES:
        module = importlib.import_module(name)
        assert module.__doc__
