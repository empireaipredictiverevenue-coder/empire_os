# Empire AI Data Handler — Permit/Market Intelligence upgrade LIVE

**18 October 2026 | Canonical EmpireOS source commit `bebd3d9f` | Exact seven-file source promotion, no service restart.**

## Outcome and verified evidence

The existing five-minute department cycle now runs a significantly stronger first-pass intelligence join:
- Official NYC DOB permit intake: original **filing**, actual **issuance**, official source run date, source first-imported time and observed/refresh time remain independent.
- Official source URL and numeric job reference must agree; invalid/trick URLs and future conflicting event dates fail closed.
- Original work codes supply *bounded hypotheses* only (e.g. PL plumbing, EL electrical); an A1/A2 source class is **not automatically roofing or solar**.
- Government BBL/BIN property references are retained but not misrepresented as verified real estate ownership or independent weather/condition evidence. Owner and permittee roles remain distinct.
- The **existing Market GPS** NYC aggregate buyer/reply/approved-buyer data inform research priority; market-level evidence never establishes a project-specific buyer.
- At most three private, sanitized official-source review dossiers travel in the existing department evidence packet. No contact names, phones, raw street addresses or free text are included.
- Old/new source-semantic SHA fingerprint distinguishes a genuine official filing/issuance/status update from an expiring 24-hour rolling count. No new bus, DB, agent, scheduler, provider call or outbound.

The previous `signal_resolver.py` permitted a complete permittee identity to become a canonical prospect from a historical permit regardless of actual event age. It now checks exact NYC official source provenance and a genuine recent filing or issuance before allowing that source-specific prospect promotion. This does **not** block independently verified business acquisition from other sources. No past CRM records were rewritten.

## Actual live data and source truth, 18 October

Existing read-only source packet `runtime/departments/source_intelligence_latest.json`, automatically produced by scheduled department cycle at ~09:06 UTC:

- **7,765** retained NYC permit source signals at the cycle time (source set may increase).
- **62** records first imported during the preceding rolling 24h.
- **62** of these are historical original project filings/issuances; **0** pass the authentic event-date recency test (30 days).
- **62** have syntactically valid official portal job URLs.
- **55** indicate an owner business label in source, **20** indicate a permittee business label: labels are NOT independently verified legal identities and none was exported in a team packet.
- **62** include building-reference identifiers, NOT proof of property ownership or damage.
- Original source run dates are recent but many filing dates range back to 1998–2023. No new work is inferred merely because the scraper downloaded a refreshed government row today.
- Existing NYC General Contractor Market GPS shows commercial demand `not_observed`, with **zero approved buyers** in that observed corridor. This aggregate is not a per-project market match.
- **Revenue from this data: zero verified.**

## Actual automatic team receipts

The new fingerprint/evidence changes produced exactly two specialist work items during the live scheduled cycle, not 62 duplicate prospects or an entire new agent department:

1. `dept_work_d8fdc90120a97f19214ad879`: `market_intelligence`, historical official project and source-quality review. Verified state **DONE**, `project_intelligence_review` present, cohort historical count 62, `semantic_model_review_performed=false`.
2. `dept_work_73b62f9d00259ecaa25e797e`: `product`, property/project identity review sharing the same underlying 62; verified state **DONE**, project intelligence summary attached, no double count, `semantic_model_review_performed=false`.

The records are in the existing `runtime/departments/work/done` queue. DONE means *first-pass source analysis recorded and delivered*, not an independently completed project dossier or authenticated paying buyer.

## QA and authority

Source + existing department/permit/CRM regression suite **67 passed** on the canonical source tree; four more adjacent product integration files returned **7 passed** in addition, no blocking failures. Future-date conflicts, old imported permits, untrusted URLs, duplicate role assumptions, bounded dossier output and personal-data exclusion were tested. All observed business authority remains `none`: no unsolicited mail, checkout, payments, fresh consumer traffic, quote, independent sale or revenue recognition.

The existing local Qwen 1.5B model is available, but department model tokens are **not configured in the existing budget policy**. The live Data Handler therefore performs zero-model-cost deterministic evidence triage. Semantic model research is coded separately as a guarded shadow feature and was **NOT invoked** for these permit rows. Do not represent the reviewed historical permits as LLM-generated new construction leads.

## Exact next sources/features to complete

1. Use genuine **permit filing and issuance event dates**, not only NYC DOB source-run timestamps, to pull actually current project changes. Source freshness, official record state, rights and coverage need independent QA.
2. Detect newly issued/amended official events on **already ingested project records**, not only fresh imports. Feed the revised event through the same stable source-semantic fingerprint and existing team review receipt.
3. Build an actual company/building dossier only with independently corroborated property/legal business identity, relevant construction speciality and current source link. Check against approved Market GPS buying capacity; if missing, deliver to Market/Product for research, not Sales.
4. Cross-check real geospatial and time-aligned Storm/Warehouse/Property intelligence on the exact subject, never infer damage or insured claims from vicinity/weather alone.
5. Enable bounded semantic local AI research only after explicit existing department model budget; keep model hypotheses independently verifiable.
6. Carry the same verified-data contract to UK planning, roofing carrier networks, industrial/warehouse assets, solar/HVAC and mass-tort firm-level research. Continue prospecting and product building **in parallel**.

Primary technical handoff: `docs/architecture/DATA_HANDLER_PERMIT_MARKET_INTELLIGENCE_UPGRADE_20261018.md`.
Earlier automatic source routing: `docs/evidence/SOURCE_INTELLIGENCE_AUTOMATIC_TEAM_HANDOFF_20261017.md`.
