# EmpireOS JEV GTM V2 — Wave 8 First-Party Official Source Continuity

Date: 2026-10-14
Starting isolated branch commit: `4780fa22`
Branch: `feature/jev-gtm-v2-20261014`
Mode: OBSERVE; zero paid API spend; no production deployment, outbound, database migration, CRM write, contact permission, model calibration or recognized revenue.

## Operational defect reproduced

Wave 7's bounded public search pilot returned `INSUFFICIENT_PRIMARY_EVIDENCE`: zero original pages inspected. Checked the pilot's isolated health file:
`/tmp/empire_jev_public_research_smoke_20261014.json`.

Actual public recovery state: `consecutive_failures=2`, `last_state=CIRCUIT_OPEN`, no last success. This is search-provider availability, *not* evidence of no buyer demand. Production Search Fabric circuit thresholds, cooldown and provider selection remain unchanged.

## Correction: explicit primary-source continuity, not circuit evasion

Reused previously independently authored research inspector from the separate isolated Vane/OpenManus/Odysseus intake:
- `empire_os/research/public_page_inspector.py`
- `tests/research/test_public_page_inspector.py`

Inspector protects HTTPS hostname using pinned globally routable DNS resolution, host-verified TLS, short timeout, no redirects, max ~192 KiB HTML read, no code execution and no hidden browser shell. It does not authenticate page claims or detect buyer intent, and does not replace site-specific robots/license checks.

Enhanced the existing `empire_os.research.deep_research_intake.run_research` and profile/adapter interfaces:
- New explicit `operator_primary_urls` maximum **3**, counted in the same globally bounded page budget, unique, safely normalised, HTTPS only.
- `skip_discovery=True` available *only* when an operator supplies actual primary URLs. No calls to any search engine and no fake search event. The existing circuit breaker is neither changed nor bypassed.
- Primary pages are tagged `operator_supplied_primary_source`; search-discovered pages remain tagged `public_search_result`. Both require the same page-inspection callback and remain factually unverified.
- Reject invalid URL lists or budgets before tool calls; source evidence remains identified by inspection URL and content hash. Duplicate discovered/selected pages are inspected at most once.

Enhanced `empire_os.jev_gtm_research_bridge`:
- Explicit `official_source_urls` and `source_only` flags with strict operator source allowlist: `gov.uk`, `*.gov.uk`, `ons.gov.uk`, `*.ons.gov.uk`. No named prospect URLs, private metadata endpoints, credentials or arbitrary URL sources.
- `inspect_jev_official_source` wraps the already reviewed pinned-IP official-page inspector.
- `run_jev_official_source_review` invokes the shared research pipeline with no search-provider calls; accepts optional inspector injection only for isolated tests.
- As before, research packets expose only URL, public hostname, inspection status, content SHA-256, source provenance and cited-claim hash. Source text, message content and unverified model claims are not promoted into JEV or the CRM.
- Never clears suppression, authorizes an email, authenticates original inbound replies, declares a buyer's interest, adjusts a sales score or alters JEV decision authority.

Enhanced the existing one-shot research operator `scripts/probe_jev_evidence_research_v2.py`:
- New explicit `--official-source-smoke --official-source-url URL --public-niche ... --public-market ...` one-shot public source read with synthetic-only JEV input, no database, no sends, no paid search.
- Default `--fixture-smoke` and local JSON *plan-only* modes remain unchanged.
- Founder read API status and standalone JEV page include code-ready/source continuity truth flags, explicitly `production_enabled=false`. No autonomous executor or new public route.

## Independent source evidence and live read

Public official URL independently identified:
`https://www.ons.gov.uk/businessindustryandtrade/constructionindustry/bulletins/constructionoutputingreatbritain/latest`.

A real read-only HTTPS primary-page inspection from the remote EmpireOS host, with synthetic JEV input, returned:
- `status=EVIDENCE_READY_FOR_SYNTHESIS`
- `source_count=1`
- `inspected_source_count=1`
- `source_inspection_status=ORIGINAL_HTML_HEADINGS_INSPECTED`
- `content_fingerprint_present=true`
- `searches_executed=0`
- `pages_considered=1`
- `buyer_intent_verified=false`
- `commercial_promotion_authorized=false`
- `outbound_sent=false`, `database_write=false`.

This verifies **the specific public primary page was accessible and hashable at that moment**. It does not establish content truth, a real business opportunity, dated buyer intent, model calibration, search discovery health or cross-source coverage. We did not extract operational contact information or create a CRM record.

## Acceptance tests

- New `tests/test_jev_official_source_continuity.py`: real source-only no-search behaviour, offline provider outage, redirect/SSRF URL refusal, DNS-pinned inspector guard, duplicate URL dedupe, bounded page budget, failed inspection safe abstention, inability to escalate source evidence.
- Existing copied `tests/research/test_public_page_inspector.py`: mocked DNS/IP and first-party HTTPS controls.
- Existing JEV bridge/operator and shared research tests remain mandatory; and wider suite must pass before release.
- TypeScript compiles under existing installed frontend dependencies.
- No dependency installs, runtime timer, agent registry entry, Cloudflare changes, cost, provider circuit reset or privileged DB login.

## Production gates untouched

1. This is branch-only; deployment and link insertion into active Founder Console not performed.
2. Live original-source *inspection* is demonstrated, but real market discovery and grounded commercial entity connections are not proven.
3. Migration 051 remains prepared-only; canonical tenant CRM proof, original authenticated inbound provider receipts and customer buying conversations require the separate existing owners.
4. Full research model calibration and independently labelled benchmark sets remain pending.
5. Real buyer conversations and realised revenue require commercial evidence independent of a public report.

Outcome: the specific **zero-source outage continuity gap is technically fixed for explicitly selected official public primary documents**, without weakening source controls or claiming a verified buyer.
