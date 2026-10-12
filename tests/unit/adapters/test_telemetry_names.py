"""Telemetry names are spelled out only in attributes.py."""

import ast
from pathlib import Path

from costwise.adapters.telemetry import attributes as attr

_ROOT = Path(__file__).resolve().parents[3]
_ALLOWED = _ROOT / "src" / "costwise" / "adapters" / "telemetry" / "attributes.py"
_PREFIXES = ("neatlogs.", "gen_ai.")


def _string_constants(path: Path) -> list[str]:
    """Return every string constant in a Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def test_no_module_hard_codes_telemetry_attribute_names() -> None:
    """Only attributes.py may contain a string starting with neatlogs. or gen_ai."""
    offenders = []
    for folder in ("src", "scripts"):
        for path in sorted((_ROOT / folder).rglob("*.py")):
            if path == _ALLOWED:
                continue
            hits = [s for s in _string_constants(path) if s.startswith(_PREFIXES)]
            if hits:
                offenders.append(f"{path.relative_to(_ROOT).as_posix()}: {hits}")
    assert offenders == []


def test_attribute_names_use_filterable_namespaces() -> None:
    """Custom attributes are neatlogs.workflow.* or neatlogs.session.*; flags are strings."""
    custom = [
        attr.CONFIG_VERSION,
        attr.TASK_CATEGORY,
        attr.SUCCESS,
        attr.COST_MODEL_USD,
        attr.RUN_ID,
    ]
    assert all(name.startswith(("neatlogs.workflow.", "neatlogs.session.")) for name in custom)
    assert (attr.flag(True), attr.flag(False)) == ("true", "false")
