# Empire AI original acquisition analytics: channel-stage upgrade
27 October 2026 | Existing Analytics054/055 / original first-party contract

## What was built
Expanded `empire_os/analytics/first_party_event_contract.py`—**the original Analytics programme**, not a new service—to share one strict, consent- and source-authority validation path between:
- `simulate_verified_batch`: unchanged public simulation output, previously overall totals only.
- **NEW** `simulate_channel_stage_presence`: the same validated, event-nonce-deduplicated, source-resolved events grouped into the **six originally approved channel classes** (`direct`, `organic_search`, `organic_social`, `email`, `referral`, `unknown`).

The new output contains a fixed channel roster with stage *presence* counts: distinct simulated sessions containing `page_view`, `engagement`, `cta_click`, `form_start` or `form_submit_attempt`. These are NOT ordered stages, unique people, accepted enquiries, qualified CRM leads, payments, revenue or valid percentages. A `form_submit_attempt` explicitly remains an attempted action and is never called a sale.

A per-channel **5-session minimum display guard** suppresses any small simulated cohort rather than displaying identifying session counts. This is an offline display control, NOT a guarantee of privacy, lawful consent, resistance to repeated-query differencing, or a production reporting policy. Every input still requires a server-side simulation of consent and source; browser-defined channels or consent, URL query strings, raw referrers, person identifiers, IP, payment fields and unexpected event names are rejected. An unknown/revoked session invalidates the *whole* batch. Callbacks run only once per distinct session, with zero partial outputs on failure.

The original existing `OfflineSessionAuthority` is exercised end to end in regression tests: sessions are opened with trusted source types, independently granted in the simulation, aggregated through the exact contract, then a revocation invalidates the affected batch and suppresses the reduced cohort. Replayed event nonces are deduplicated, conflicting replays are rejected.

## Critical real-world limitations
- Entire feature is `SIMULATION_ONLY`; **zero** real sessions, leads, conversion rates, call records, attributed revenue or campaign ROI inferred.
- Original held migration `migrations/empiredb/054_first_party_analytics_ledger_held.sql` restricts `acquisition_channel` to six existing classes; the 055 erasure controls are separately held. The new evaluator honors those exact classes.
- Original PPC/traffic research may refer to paid search, paid social, affiliate partners, publisher referrals or phone inbound. Those source names are **NOT** automatically consented, authenticated Analytics channel labels. A formal versioned privacy + EmpireDB schema/source-evidence migration and caller-source identity protocol are required before admission. Do not misclassify paid traffic as organic to force reporting.
- Tag Intelligence proves static markup only, not real browser collection, secure session authority, lawful site analytics consent, authenticated CRM transactions, payment outcomes or predictive revenue.
- Do not use a test fixture or this simulation response to seed production CRM, dashboards, settlement ledgers, ad bidding or Economic Memory.

## Existing-owner path to working acquisition → conversion → revenue
1. Original Website/Privacy/Analytics owners jointly approve purposes, cookies/consent handling, source retention and erasure. Review existing first-party session ledger and authentic signed-source classification; **do not trust browser claims**.
2. Original EmpireDB owner inspects Analytics054/055 catalog state, owner/RLS, revocation and erasure; authorises a **reviewed** publication/collection release only when legal and tenant bindings are independently proved.
3. Original GTM owner proposes a versioned mapping for paid/affiliate/video campaigns using independently verified, short-lived source evidence and separate consent. A new `acquisition_channel` enum/check constraint and corresponding event/session authority changes require approved migration; do not mutate the original six-source v1 contract opportunistically.
4. Original CRM owner supplies independently verified, purpose-compatible, tenant-bound **accepted** conversion outcomes through the existing canonical CRM and suppression rules. An event nonce is **not** a contact or an outreach instruction.
5. Original Finance/CRU owner independently verifies bank or payment settlement, actual spend/costs, reversals and same-cohort attribution; UNKNOWN remains UNKNOWN.
6. Existing Predictive Revenue owner can then calibrate real channel conversion, customer LTV/churn and net margin using independently authenticated outcomes, not the simulation's stage-presence counts.

## Tests and scope
`tests/analytics/test_offline_channel_stage_presence_20261027.py`: six-class session deduplication, event stage presence, low-sample suppression, replay safety, malicious field rejection, unknown channel/consent holds and revocation through original `OfflineSessionAuthority`.

Related original event/session/ingress/measurement tests were run. No database modification, new daemon, agent, ingress mount, website release, ad spend, external send, buyer route or credential access performed. This workstream does not own or touch Lead Smart.
