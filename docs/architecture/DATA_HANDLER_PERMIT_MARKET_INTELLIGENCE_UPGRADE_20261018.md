# Empire AI — Data Handler intelligence upgrade

**18 October 2026 | Existing EmpireOS Source Intelligence, Permit, Property and Market GPS**

## Actual problem fixed

The automatic source router was correctly detecting newly imported NYC permit records but could not distinguish source collection from actual project chronology. At 08:40–08:57 UTC, 62 NYC permit rows had been **first imported within 24 hours**; all 62 original filing dates were **more than one year old**, and none of their issuance dates was a current event. Some had a current `dobrundate` despite originating from 1998–2023 filings. These are NOT 62 new construction leads.

Previous permittee-identity resolution could also create a canonical company prospect with a strong source ID and phone without checking whether the official permit event was recent. That could contaminate sales-oriented opportunity context.

## What is now implemented in the existing software

**Source -> source-evidence quality -> cross-intelligence -> department review**, using only already deployed infrastructure.

- New read-only `empire_os/permit_project_intelligence.py` reads the existing `runtime/acquisition/signal_inbox.json` (no API traffic, DB mutation, provider costs, timers or new service).
- Separately parses **actual filing**, **actual issuance**, **official data-source run date**, **first collected**, and **last source observed**. A recent import/portal run does not create a recent project. Invalid, missing, future and conflicting dates are not eligible for fresh-project review.
- Requires an exact HTTPS NYC official `PropertyOverflowDetails.jsp?job=...` record URL and matching numeric job reference. URL shape/provenance is *not* independent verification of the underlying record's accuracy or that the site is under construction today.
- Uses filing/work codes only as limited sector hypotheses; A1/A2/NB are *not* automatically roofing/solar opportunities. Direct PL/EL work codes can identify plumbing/electrical category; all else remains general/unknown unless corroborated.
- Preserves official BBL and BIN building reference identifiers but marks property identity as **SOURCE_REFERENCE_ONLY**, never verified property ownership/condition. Owner and permittee business presence are separate flags; actual names, phones, addresses and free-text descriptions do **not** enter the review packet.
- Reads the already existing **Market GPS** NYC business/contractor market snapshots when fresh. Reports market-wide observed replies, approved buyer counts and demand state, but never maps aggregate sales signals to an individual permit/customer. Current NYC General Contractor market data were `not_observed` demand, **0 approved buyers**.
- Bounded per-cycle source analysis (at most 3 private project review dossiers), stable source-semantic SHA fingerprint over trusted event fields, normal time-window counts excluded from repeated queue triggers. Meaningful new issuance, filing or stage changes can cause a new department task.
- Adds the sanitized report to the existing private source-intelligence packet and attaches at most three project reviews to the existing Permit team's first-pass receipt, with a summary-only view for Property to avoid double-counting.
- Uses the **same original-event gate** for `signal_resolver.py` before a company can be treated as a project-sourced acquisition candidate. Untrusted or old permit records return a deferral reason before canonical prospect writes. This does **not** block independently sourced legitimate company prospecting through other existing acquisition lanes.
- All routing remains OBSERVE with no contact, sales promotion, lead purchase, guarantee, mainnet, payment, insurance claim, or recognized revenue. No paid or local AI model invoked by this deterministic upgrade.

## Evidence from real live input

At the inspected 18 October checkpoint (precise counts change as the crawler continues):
- First-imported permit cohort: **62** records.
- Official portal record URL validated syntactically: **62**.
- Actual filing or issuance within the last 30 days: **0**.
- Historical (actual filing/issuance) source rows: **62**.
- Rows exposing a source BBL/BIN building identifier: **62**, property ownership not independently proven.
- Owner business label present in raw source: **55**; permittee business label present: **20**; no name/contact was promoted as verified.
- Bounded historical review examples safely produced, citing their actual NYC job reference and actual filing dates. They are documentation/source-quality examples, **not** a sales shortlist.
- Current Market GPS for NYC general contractors: aggregate market research, **no observed commercial demand** or paying buyer connection.

## Test and release contract

Run the existing focused / regression suites, including:
`tests/test_permit_project_intelligence_20261018.py`,
`tests/test_permit_project_department_integration_20261018.py`,
`tests/test_signal_resolver.py`,
`tests/test_source_intelligence_department_handoff_20261017.py`,
`tests/test_department_cycle.py`,
`tests/test_department_worker.py`,
`tests/test_department_work_queue.py`,
`tests/test_permit_intelligence_runtime.py`,
`tests/test_founder_vertical_intelligence_api.py` and
`tests/test_opportunity_loop.py`.

**67 tests passed** on the isolated branch before promotion; production recheck must be repeated. No raw test leads are posted into EmpireDB. Existing source event router and work queue remain owned by their current service; no extra database or service. The original live source snapshot and queue state must be inspected after release and only genuine meaningful changed evidence may enqueue new review jobs.

## Next intelligence upgrade after this slice

1. Get actual NEW official filings/issuances from permitted NYC DOB and UK planning sources by indexing **event date**, not merely the source run timestamp. Record freshness/error/rights and source URL.
2. Enrich only a small verified project cohort with **original building ID/Company House or official ownership links**, industry/event specificity and authenticated source provenance.
3. Cross-match genuine source-bound property and weather evidence where subject/time/geography join is *independently verified*; weather exposure is not inferred insured damage.
4. Once the existing department token budget permits, run bounded local Qwen model analysis on *only the sanitized evidence packet*, as hypotheses with source-checking—not autonomous lead/revenue claims. The LLM shadow contract already exists but remains inactive under the ledger.
5. Send legitimate business opportunities to qualified CRM/Buyer team only after original source, individual company's identity, buying use case, recipient suppression and independently confirmed payer capacity. Never auto-send.
6. Continue Warehouse, carrier-contractor repair programmes, Permit/Property, private-capital and mass-tort data lanes in parallel via the existing Source Intelligence OS and existing departments.

**Commercial result at release: no new buyers or revenue were established by this data improvement.** This is a reliability and intelligence milestone that keeps bad historical data from misleading the sales team.
