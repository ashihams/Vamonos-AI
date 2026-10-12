# costwise report: demo-2

Baseline is config v1; the final accepted config is v3. The baseline ran 28 tasks (23 evaluation, 5 held-out). Costs and p95 latency cover every task in a version; success rates are per split.

## Cost

| Metric | Baseline v1 | Final v3 | Change |
| --- | --- | --- | --- |
| Cost per successful task, USD [source: model + infra + data] | 0.106967 | 0.106976 | +0.0% |
| Model cost, USD [source: measured tokens x configured prices] | 2.886484 | 2.886764 | +0.0% |
| Infra cost, USD [source: modeled from local wall time] | 0.001621 | 0.001589 | -2.0% |
| Data cost, USD [source: modeled from fixture credits x configured price] | 0.000000 | 0.000000 | n/a |
| Total cost, USD [source: model + infra + data] | 2.888104 | 2.888353 | +0.0% |

## Quality and latency

| Metric | Baseline v1 | Final v3 |
| --- | --- | --- |
| Success rate, evaluation split | 95.7% | 95.7% |
| Success rate, held-out split (never shown to the optimizer) | 100.0% | 100.0% |
| p95 latency, ms (cold starts excluded) | 5636 | 5771 |

## Iterations

| # | Lever | New value | Decision | Kept | Reason |
| --- | --- | --- | --- | --- | --- |
| 1 | routing | {"default_tier": "cheap", "strong_if_missing_fields_gte": 2, "strong_if_near_threshold": false} | approved (auto-approved) | no | guardrails failed: eval_success, heldout_success |
| 2 | cache_company_data | true | approved (auto-approved) | yes | guardrails passed |

Every evaluated version, including rolled-back ones, is in `trajectory.csv`; `trajectory.mmd` charts cost per successful task across them.

## What is measured and what is modeled

- Model cost is measured: each call's input and output token counts as reported by the model endpoint, times the per-token prices in `config/pricing.yaml`. The prices are configuration, not a bill.
- Infra cost is modeled: tasks ran on this machine, so the Lambda price formula is applied to local wall time and the configured memory. It is not a bill, and the memory lever was not available.
- Data cost is modeled: the Crustdata credits recorded when each company fixture was fetched, times the per-credit price in `config/pricing.yaml`. Companies come from frozen fixtures; a repeated company is a cache hit only when the cache lever is on.
- Data cost is zero because `crustdata_usd_per_credit` is 0.00: the Crustdata credits were free under the hackathon allowance. A paying customer would pay per credit, so real unit costs are higher than shown.
- Held-out companies are never shown to the optimizer or the approver. Their success rate is reported separately and is one of the guardrails.
- Success means the model's fit answer matches a label from the rule-based ICP check, not a human judgment.
