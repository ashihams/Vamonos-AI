"""Rejections remembered across runs that share a starting config."""

from costwise.domain.config import Lever
from costwise.domain.proposals import ApprovalDecision, IterationRecord
from costwise.services.history import earlier_rejections
from tests.testing_fakes import InMemoryConfigStore, InMemoryRunStore
from tests.unit.domain.builders import make_config
from tests.unit.services.report_support import record

APPROVED = ApprovalDecision(approved=True, note="")
CHEAP_ROUTING = {"strong_if_missing_fields_gte": 2}


def _rejected(lever: Lever, value: bool | int | dict[str, int]) -> IterationRecord:
    """Return a rolled-back iteration for lever and value."""
    return record(1, lever, value, APPROVED, (2, False, "guardrails failed: eval_success"))


def test_collects_rejections_from_runs_with_the_same_start() -> None:
    """Rejected proposals from other runs with the same v1 config are returned; others not."""
    runs, configs = InMemoryRunStore(), InMemoryConfigStore()
    start = make_config()
    configs.save("same-start", start)
    runs.save_iteration("same-start", _rejected(Lever.ROUTING, CHEAP_ROUTING))
    kept = record(2, Lever.CACHE, True, APPROVED, (3, True, "guardrails passed"))
    runs.save_iteration("same-start", kept)
    configs.save("other-start", start.model_copy(update={"max_output_tokens": 256}))
    runs.save_iteration("other-start", _rejected(Lever.MAX_OUTPUT_TOKENS, 128))
    runs.save_iteration("no-config", _rejected(Lever.CACHE, True))
    configs.save("current", start)
    runs.save_iteration("current", _rejected(Lever.MAX_OUTPUT_TOKENS, 384))

    found = earlier_rejections(runs, configs, "current", start)

    assert [(p.lever, p.new_value) for p in found] == [(Lever.ROUTING, CHEAP_ROUTING)]


def test_no_other_runs_means_no_rejections() -> None:
    """A first run starts with a clean slate."""
    found = earlier_rejections(InMemoryRunStore(), InMemoryConfigStore(), "first", make_config())
    assert found == ()
