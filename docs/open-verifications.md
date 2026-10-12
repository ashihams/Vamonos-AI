# Open verifications

## TODO(VERIFY: Crustdata credits charged per company enrich call)

- Where: `src/costwise/adapters/data/crustdata_client.py`, `CREDITS_PER_ENRICH = Decimal(2)`.
- Source so far: the Crustdata pricing page lists `/company/enrich` at 2 credits per record, plus 2 when `technographics` is requested. costwise does not request `technographics`.
- Still unchecked: what the dashboard actually charged for the 2026-10-11 `retool.com` call, and whether a no-match call is billed.

## TODO(VERIFY: LiteLLM proxy accepts max_tokens and returns usage for the chosen models)

- Where: `src/costwise/adapters/llm/openai_compatible.py`.
- Source so far: the neatHack models page gives the base URL `https://litellm.vision.aivar.app/v1`, Bearer auth, the OpenAI-compatible `/chat/completions` route, and reads `choices[0].message.content`. The client also sends `max_tokens` and `temperature` and reads `usage.prompt_tokens` and `usage.completion_tokens`, as the build spec requires.
- Still unchecked: no live call yet, because the team key has not been claimed. Confirm one Nova and one Claude call return `usage`, and that `max_tokens` is honored.

## Model names and per-token prices (config values, not code markers)

- Where: `config/pricing.yaml` and `config/policy.yaml` still hold `<cheap-model-name>`, `<strong-model-name>`, and `"0.00"` prices.
- Available on the shared key (models page, 2026-10-12): `nova-micro`, `nova-lite`, `nova-pro`, `nova-2-lite`, `claude-haiku`, `claude-sonnet-4.6`, `claude-opus-4.6`. The page publishes no prices.
- Waiting on the builder to pick the cheap and strong pair and the price source.

## Crustdata USD price per credit (config value, not a code marker)

- Where: `config/pricing.yaml`, `crustdata_usd_per_credit: "0.00"`.
- The docs give credits per call but not a dollar price per credit. The hackathon credits are free to participants, so the cost model needs a stated assumption before data cost is reported.

## Checked against the docs and one live call (2026-10-11)

- Endpoint `POST https://api.crustdata.com/company/enrich`, header `authorization: Bearer <key>`, header `x-api-version: 2025-11-01`.
- Response: top-level array of `{matched_on, match_type, matches: [{confidence_score, company_data}]}`. No match is `200` with `matches: []`; the spec also defines `404`.
- `fields` must list every section besides `basic_info`. costwise requests `basic_info, headcount, funding, hiring, taxonomy`.
- Field mapping used by `crustdata_mapper.py`: `headcount.total`, `funding.last_round_type` (values like `series_c`), `funding.total_investment_usd`, `hiring.openings_count`, `taxonomy.professional_network_industry`, `headcount.growth_percent.six_months`.
- `hiring.openings_count` counts all open roles. The response has no engineering-only open-role count, so `engineering_open_roles` holds total openings.
