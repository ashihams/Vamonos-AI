"""Ask the strong model for one lever change as strict JSON, with one repair attempt."""

import json
import logging
from collections.abc import Sequence

from pydantic import ValidationError

from costwise.domain.analysis import RunSummary
from costwise.domain.company import COMPANY_FIELD_NAMES
from costwise.domain.config import (
    ALLOWED_MEMORY_MB,
    MAX_MISSING_FIELDS,
    MAX_OUTPUT_TOKENS,
    MIN_MISSING_FIELDS,
    MIN_OUTPUT_TOKENS,
    Lever,
    OptimizerConfig,
)
from costwise.domain.errors import ConfigError, LLMError
from costwise.domain.proposals import Proposal, validate_proposal
from costwise.ports.llm import LLMClient, LLMRequest
from costwise.services.parsing import strip_code_fence
from costwise.services.proposers import is_rejected

PROPOSER_PROMPT_VERSION = "propose-v1"
MAX_PROPOSAL_TOKENS = 400

SYSTEM_PROMPT = """\
You tune a company-qualification app to lower its cost without lowering its accuracy.
Propose exactly one change to one lever.

Reply with one JSON object and nothing else, with exactly these keys:
- "lever": one of the available levers
- "new_value": the new value for that lever, in the format below
- "rationale": one or two sentences citing numbers from the run summary
- "predicted_cost_change_pct": a number, negative for a saving
- "risk": "low", "medium", or "high"

Lever value formats:
- "routing": {{"default_tier": "cheap" or "strong", \
"strong_if_missing_fields_gte": integer {min_missing} to {max_missing}, \
"strong_if_near_threshold": true or false}}
- "payload_fields": null for the full payload, or a list of distinct names from: {fields}
- "max_output_tokens": integer {min_tokens} to {max_tokens}
- "cache_company_data": true or false
- "lambda_memory_mb": one of {memory}

The new value must differ from the current config and must not repeat a rejected proposal.
"""

USER_PROMPT = """\
Current config:
{config}

Run summary (evaluation split only):
{summary}

Available levers: {levers}

Rejected proposals:
{rejected}
"""

REPAIR_PROMPT = """\
{user}
Your previous reply was rejected: {error}
Previous reply:
{reply}

Reply again with one corrected JSON object.
"""

_LOG = logging.getLogger(__name__)


def _system_prompt() -> str:
    """Render the system prompt with the current bounds."""
    return SYSTEM_PROMPT.format(
        min_missing=MIN_MISSING_FIELDS,
        max_missing=MAX_MISSING_FIELDS,
        fields=", ".join(sorted(COMPANY_FIELD_NAMES)),
        min_tokens=MIN_OUTPUT_TOKENS,
        max_tokens=MAX_OUTPUT_TOKENS,
        memory=", ".join(str(size) for size in sorted(ALLOWED_MEMORY_MB)),
    )


def _user_prompt(
    config: OptimizerConfig,
    summary: RunSummary,
    available: frozenset[Lever],
    rejected: Sequence[Proposal],
) -> str:
    """Render the evidence the model decides from."""
    return USER_PROMPT.format(
        config=config.model_dump_json(),
        summary=summary.model_dump_json(),
        levers=", ".join(sorted(lever.value for lever in available)),
        rejected=json.dumps([proposal.model_dump(mode="json") for proposal in rejected]),
    )


class LLMProposer:
    """Strong-model proposer that returns None instead of an invalid proposal."""

    def __init__(self, llm: LLMClient, model: str) -> None:
        """Use llm with the named model."""
        self._llm = llm
        self._model = model

    def propose(
        self,
        config: OptimizerConfig,
        summary: RunSummary,
        available: frozenset[Lever],
        rejected: Sequence[Proposal],
    ) -> Proposal | None:
        """Return a valid, new proposal, repairing once, or None."""
        _LOG.info("optimizer prompt version=%s", PROPOSER_PROMPT_VERSION)
        system = _system_prompt()
        user = _user_prompt(config, summary, available, rejected)
        try:
            reply = self._ask(system, user)
            proposal, error = _check(reply, config, available, rejected)
            if proposal is not None:
                return proposal
            repair = REPAIR_PROMPT.format(user=user, error=error, reply=reply)
            proposal, error = _check(self._ask(system, repair), config, available, rejected)
        except LLMError as exc:
            _LOG.warning("optimizer model call failed: %s", exc)
            return None
        if proposal is None:
            _LOG.warning("optimizer proposal invalid after repair: %s", error)
        return proposal

    def _ask(self, system: str, user: str) -> str:
        """Make one deterministic call and return its text."""
        request = LLMRequest(
            model=self._model,
            system=system,
            user=user,
            max_output_tokens=MAX_PROPOSAL_TOKENS,
            temperature=0.0,
        )
        return self._llm.complete(request).text


def _check(
    reply: str,
    config: OptimizerConfig,
    available: frozenset[Lever],
    rejected: Sequence[Proposal],
) -> tuple[Proposal | None, str]:
    """Return the proposal, or None and the reason it cannot be used."""
    try:
        proposal = Proposal.model_validate_json(strip_code_fence(reply))
    except ValidationError as exc:
        return None, f"not a valid proposal object ({exc.error_count()} errors)"
    try:
        validate_proposal(proposal, config, available)
    except ConfigError as exc:
        return None, str(exc)
    if is_rejected(proposal, rejected):
        return None, "this exact proposal was rejected before"
    return proposal, ""
