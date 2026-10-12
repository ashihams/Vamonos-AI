# costwise report: golden-run

Baseline is config v1; the final accepted config is v2. The baseline ran 4 tasks (3 evaluation, 1 held-out). Costs and p95 latency cover every task in a version; success rates are per split.

## Cost

| Metric | Baseline v1 | Final v2 | Change |
| --- | --- | --- | --- |
| Cost per successful task, USD [source: model + infra + data] | 0.019333 | 0.014000 | -27.6% |
| Model cost, USD [source: measured tokens x configured prices] | 0.040000 | 0.024000 | -40.0% |
| Infra cost, USD [source: modeled from local wall time] | 0.002000 | 0.002000 | +0.0% |
| Data cost, USD [source: modeled from fixture credits x configured price] | 0.016000 | 0.016000 | +0.0% |
| Total cost, USD [source: model + infra + data] | 0.058000 | 0.042000 | -27.6% |

## Quality and latency

| Metric | Baseline v1 | Final v2 |
| --- | --- | --- |
| Success rate, evaluation split | 66.7% | 66.7% |
| Success rate, held-out split (never shown to the optimizer) | 100.0% | 100.0% |
| p95 latency, ms (cold starts excluded) | 400 | 400 |

## Iterations

| # | Lever | New value | Decision | Kept | Reason |
| --- | --- | --- | --- | --- | --- |
| 1 | cache_company_data | true | approved (auto-approved) | yes | guardrails passed |
| 2 | routing | {"strong_if_missing_fields_gte": 2} | approved (try it \| watch held-out) | no | guardrails failed: eval_success, heldout_success |
| 3 | max_output_tokens | 256 | declined | no | rejected by approver |

Every evaluated version, including rolled-back ones, is in `trajectory.csv`; `trajectory.mmd` charts cost per successful task across them.

## What is measured and what is modeled

- Model cost is measured: each call's input and output token counts as reported by the model endpoint, times the per-token prices in `config/pricing.yaml`. The prices are configuration, not a bill.
- Infra cost is modeled: tasks ran on this machine, so the Lambda price formula is applied to local wall time and the configured memory. It is not a bill, and the memory lever was not available.
- Data cost is modeled: the Crustdata credits recorded when each company fixture was fetched, times the per-credit price in `config/pricing.yaml`. Companies come from frozen fixtures; a repeated company is a cache hit only when the cache lever is on.
- Held-out companies are never shown to the optimizer or the approver. Their success rate is reported separately and is one of the guardrails.
- Success means the model's fit answer matches a label from the rule-based ICP check, not a human judgment.
