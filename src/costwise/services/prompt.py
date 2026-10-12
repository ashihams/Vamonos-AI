"""Build the qualification prompt from the ICP rule and a company payload."""

import json
import logging
from collections.abc import Mapping

from pydantic import JsonValue

from costwise.domain.icp import IcpRule

PROMPT_VERSION = "qualify-v1"

SYSTEM_PROMPT = """\
You qualify B2B companies against an ideal customer profile (ICP).

A company fits only if all three hold:
1. Headcount is between {min_employees} and {max_employees} inclusive.
2. The latest funding stage is one of: {stages}.
3. Open roles are at least {min_roles}.

Where to read each value:
- Headcount: employee_count, or headcount.total.
- Funding stage: funding_stage, or funding.last_round_type.
- Open roles: engineering_open_roles, or hiring.openings_count.
If any of the three values is missing or null, the company does not fit.

Reply with one JSON object and nothing else. Use exactly these keys:
- "icp_fit": true or false
- "reasons": a list of short strings, one per rule checked
- "headcount_band": a headcount range such as "201-500", or null if headcount is missing
- "stage": the funding stage you used, or null if it is missing
"""

USER_PROMPT = """\
Company data (JSON):
{payload}
"""

_LOG = logging.getLogger(__name__)


class PromptService:
    """Render the system and user prompts for one qualification call."""

    def build(self, payload: Mapping[str, JsonValue], rule: IcpRule) -> tuple[str, str]:
        """Return (system, user) prompts and log the prompt version."""
        system = SYSTEM_PROMPT.format(
            min_employees=rule.min_employees,
            max_employees=rule.max_employees,
            stages=", ".join(sorted(rule.allowed_stages)),
            min_roles=rule.min_engineering_open_roles,
        )
        body = json.dumps(dict(payload), ensure_ascii=False, separators=(",", ":"))
        _LOG.info("prompt built version=%s", PROMPT_VERSION)
        return system, USER_PROMPT.format(payload=body)
