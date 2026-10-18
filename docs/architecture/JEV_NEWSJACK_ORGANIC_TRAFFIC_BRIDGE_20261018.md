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

## Wave 2 — existing research export and first-party GSC adapter

Added `empire_os/jev_newsjack_adapters.py`:

- `signals_from_last30days_agent_export` consumes **existing**
  `last30days` agent-export schema `1.2`, including source-status,
  candidate ID, dated story and a hashed immutable observation fingerprint.
  No new feed or scraping service. Timestamps without timezone are held as
  unavailable, rather than inventing publication times. Research-export
  assertions are unverified observations, never facts or lead signals.
- `attach_gsc_query_page_observations` calls the **existing**
  `GoogleSearchConsoleAdapter.observations` method with a bounded historical
  date window and the approved Empire AI Search Console property. It attaches
  data **only** when both query AND owned page exactly match explicit lookup
  mappings. A GSC row is not news-attributed traffic. The adapter does
  not declare the page live; that remains the existing website inspector's
  job. Duplicate search rows are ignored rather than summed.

This is an offline and read-only bridge and does not automatically activate
the GSC reader, fetch a remote feed, request an API key or change any service
configuration. The authenticated GSC reader's production availability must
be checked in the running Search Intelligence service environment; a shell
using default environment returned `disabled` on 18 October 2026.
This shell observation is not proof that the service's reader is disabled.

Run an already-produced `last30days` agent export with the isolated CLI:

```sh
cd /home/ubuntu/empire_worktrees/jev_newsjack_traffic_20261018
/srv/empire_os/.venv/bin/python -m scripts.review_jev_newsjack_traffic \
  --input /path/to/authorized-last30days-agent-export.json \
  --input-format last30days-agent \
  --as-of 2026-10-18T12:00:00+00:00 \
  --sector solar --market GB --include-items
```

This CLI only performs offline research-intake screening. To attach GSC
observations, the existing Search owner can explicitly call the adapter
from its authorised reader context, then feed the returned `signals` to
`review_newsjack_jev_traffic`. Local synthetic provider checks are
not live organic search evidence.

Success criteria for live traffic remain: inspected primary source,
real publication timestamp, independent corroboration, owned destination
observed live, query/page observations for the appropriate period, a review
approved by the editorial owner, and first-party referral/conversion
attribution. No claims of traffic generation until actually measured.

## Wave 3 — verified first-party Search Intelligence loopback integration

18 October 2026, exact running service: `empire-search-intelligence-api.service`
bound only to `127.0.0.1:8771`. The existing read-only
`/v1/search/search-console/status` returned enabled, configured,
available, site `sc-domain:empire-ai.co.uk` (HTTP 200). The existing
`/v1/search/search-console/observations` endpoint returned **7 rows,
5 distinct queries, 16 impressions and 0 clicks** for 2026-10-08 through
2026-10-16, with a 50-row limit. These are returned GSC query+page metrics,
not all traffic, not news-attributed traffic and not a ranking guarantee.
SERP (other than GSC) remained observation-unverified in the service's
`/health` response.

One query was `how do i know which accounts in my tam are actually ready to
buy right now` (one impression, zero clicks, position 8 in this bounded
query/page response), reported against
`https://empire-ai.co.uk/aeo/accounting/TAM/`. The page/query targeting
deserves editorial/website review, not an automatic page mutation.

Added `SearchIntelligenceLoopbackGSCReader` to reuse the authenticated
first-party read-only service rather than duplicating Google credentials.
It only requests fixed localhost paths, rejects redirects, caps responses,
requires the owned Search Console property and validates query/page rows.
An explicit manual CLI flag can enable it:

```sh
/srv/empire_os/.venv/bin/python -m scripts.review_jev_newsjack_traffic \
 --input /path/to/authorised-news-packet.json \
 --as-of 2026-10-18T12:00:00+00:00 --sector solar --market GB \
 --destination https://empire-ai.co.uk/ \
 --gsc-live --gsc-start 2026-10-08 --gsc-end 2026-10-16 \
 --include-items
```

Only signal packets with an explicit `signal_id`, `target_query` and
`destination_url` can receive an exact query/page match; results remain
read-only research recommendations. The runtime must already provide a
working first-party Search Intelligence loopback service. This addition
does not activate a scheduled worker, local classification, external NewsJack
code, or publication; it only removes the GSC credential dependency for
a separately authorised **manual** review.

A live integration smoke test matched the observed exact `empire ai` +
`https://empire-ai.co.uk/` pair and returned 6 historical impressions and
zero clicks; the news signal was a **synthetic fixture**, so no article
traffic or event opportunity was claimed. Any actual source claim still
requires real publisher evidence and editorial verification.
