"""Proposals rejected in earlier runs, so a new run does not pay to retry them."""

import logging

from costwise.domain.config import OptimizerConfig
from costwise.domain.errors import MissingStoreError
from costwise.domain.proposals import Proposal
from costwise.ports.storage import ConfigStore, RunStore

_LOG = logging.getLogger(__name__)


def earlier_rejections(
    runs: RunStore, configs: ConfigStore, run_id: str, start: OptimizerConfig
) -> tuple[Proposal, ...]:
    """Return proposals rejected in other runs that started from the same config."""
    rejected: list[Proposal] = []
    for other in runs.run_ids():
        if other == run_id:
            continue
        try:
            same_start = configs.load(other, start.version) == start
        except MissingStoreError:
            continue
        if same_start:
            records = runs.load_iterations(other)
            rejected.extend(record.proposal for record in records if not record.accepted)
    if rejected:
        _LOG.info("%d proposals rejected in earlier runs will not be retried", len(rejected))
    return tuple(rejected)
