# Empire AI / EmpireOS — NewsJack + Existing JEV Organic Traffic Bridge

Date: 2026-10-18
Branch: `feature/jev-newsjack-traffic-20261018`
Worktree: `/home/ubuntu/empire_worktrees/jev_newsjack_traffic_20261018`
Mode: isolated engineering, OBSERVE, no production activation.

## Problem closed by this slice

News research and reactive-story discovery already exist in EmpireOS, but there
was no small, explicit handoff proving whether a **dated public story** should
be researched for traffic, evaluated by our **existing JEV typed decisions**,
and eventually proposed for an existing owned destination.

The new `empire_os.jev_newsjack_traffic.review_newsjack_jev_traffic` consumes
an authorised owner-supplied array. It validates timestamps, market/sector
scope, source citations, independent corroboration attestation, an explicitly
attested live owned destination and trustworthy scoped GSC observations.

It optionally calls the existing `TypedDecisionProvider` in shadow-only mode;
it never instantiates hosted Jev, contacts another API or claims that a model
confidence is a search-volume, conversion or sales probability.

## Owners reused, not replaced

- Public news collection: existing Research / last30days / Search Intelligence.
- Verification: existing source inspector, editorial source provenance and human reviewer.
- Decisions: existing Empire JEV / TypedDecisionProvider / Laya contract.
- Traffic proposals: existing Traffic Specialist, Revenue Distribution and Search Intelligence.
- Drafts: existing Content OS and Media OS, when separately authorised.
- Measurements: existing GSC/Analytics, first-party enquiry and Economic Memory.
- No new agent, NewsJack auto-updater, feed scheduler, database or CRM writer.

External reference: https://github.com/elvisun/newsjack (MIT; skills for
detect/triage, story origin, fact-checking, PR and AI visibility). This release
does NOT vendor or install it. Actual upstream skill output adapters remain a
later, evidence-scoped integration task; NewsJack is a methodological reference.

## Stage contract

`HOLD_EVIDENCE`: invalid, duplicate, unapproved, stale or future signal.

`RESEARCH_REVIEW`: fresh scoped source evidence, but model and/or
independence, destination or observed GSC demand evidence is missing.

`NOT_RELEVANT`: typed shadow-model label rejects relevance at or above the configured confidence threshold. Lower-confidence rejection remains `RESEARCH_REVIEW`. The threshold behavior was tested against local Laya on 18 October 2026 with a fictional input.

`CONTENT_BRIEF_REVIEW`: only when all source, corroboration, live destination
and trusted search observation gates hold AND an authorised shadow JEV
provider returns `content_brief` above the configured threshold.

No stage permits publication, external outreach, indexing, paid advertising,
mail, payments, revenue recognition or any live change.

## Input example — fictional test case, not real evidence

```json
{
  "signals": [
    {
      "signal_id": "fixture:solar:1",
      "title": "Fictional solar policy headline in a test dataset",
      "sector": "solar",
      "market": "GB",
      "primary_source_url": "https://example.org/story",
      "published_at": "2026-10-17T12:00:00+00:00",
      "observed_at": "2026-10-18T08:00:00+00:00",
      "evidence_refs": ["fixture:source-capture"]
    }
  ]
}
```

Operator can provide an approved dataset for an offline no-network assessment:

```sh
cd /home/ubuntu/empire_worktrees/jev_newsjack_traffic_20261018
/srv/empire_os/.venv/bin/python -m scripts.review_jev_newsjack_traffic \
  --input /path/to/authorised-news-packet.json \
  --as-of 2026-10-18T12:00:00+00:00 \
  --sector solar --sector roofing --market GB --market US
```

Add `--include-items` for the actual recommendation evidence queue.
The CLI deliberately does not activate a provider, run a crawler or contact
any API. The function supports a separately injected, tested and approved
shadow-only provider. `destination_live_verified`,
`independent_corroboration_verified` and
`search_observation.trusted_reader_verified` must be set only by trusted
authorised input adapters, not inferred from untrusted feed text.

## Next connection points

1. Existing Search owner emits a dated, source-linked, bounded intake packet.
2. Existing first-party JEV shadow provider receives the validated review.
3. Existing GSC reader supplies real query observations and explicit provenance.
4. Existing website owner proves the intended page is live and accurately scoped.
5. Editorial owner approves briefs and channel distribution separately.
6. Existing attribution measures visits/enquiries/revenue from actual analytics.

The new module does **not** claim to complete steps 1–6 yet. Running synthetic
unit tests does not establish audience demand, traffic, rankings or revenue.

## Evidence checks

`PYTHONDONTWRITEBYTECODE=1 /srv/empire_os/.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_jev_newsjack_traffic.py tests/test_typed_decision_provider.py tests/test_typed_decision_search_observations.py`

Expected checks cover shadow-only approval, low confidence, stale or future news,
duplicate URLs, restricted markets, missing authentic reader proof, malicious
private URL references and lack of publication authority.
