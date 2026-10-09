# EmpireOS Revenue Strike: DFW contractor-commercial review

Implementation date: 9 October 2026. **Existing EmpireOS**, not a new platform or independent CRM.

## Objective and verified facts

Use the existing September DFW contractor discovery cohort as a bounded pipeline for **fixed-fee B2B marketing/opportunity-intelligence pilot research**, not a list of companies already willing to buy Empire's services. The original eight company domains are historic. The source snapshots were manually reviewed on 2026-10-09; they are NOT real-time capacity, procurement intent, verified insurer roles, regulated insurance licence status or company registration evidence.

- The seven current-site research candidates (not qualified customers) are PowerEdge, Max Exteriors, 180 Roofing, LABA, RISE, SPC, Top Notch Roofing & Restoration.
- Mastercraft historical domain redirects to a differently named Cedar Crest Roofing website: fail closed under identity-change hold. No auto-merger or cross-company contact.
- PowerEdge has an independently viewed *public company webpage* advertising sales roles; this is a growth-fit research signal, NOT confirmed buying interest. Its claimed crew/roof capacity receives zero score weight unless independently verified.
- Public business directory entries corroborate the general existence of some company names in DFW, but these do not independently prove company registration, ownership, domain control or licensing.
- Website statements around insurance claims should be reviewed under the relevant Texas rules; do not treat their marketing claims as lawful adjusting authority.

Evidence references:
- https://poweredgetx.com/careers
- https://poweredgetx.com/
- https://www.maxexteriors.com/areas/roofing-contractor-fort-worth-tx
- https://180roofing.com/service-areas/fort-worth/
- https://www.spcroofs.com/contact
- https://labaroof.com/contact
- https://www.topnotchroofingrr.com/

## Integration points — existing platform only

- `empire_os/claims_exchange/`: the previously-tested V2 candidate normalization, public site dossier, safe economics and claims/offers gates are now *copied into the original EmpireOS application*, not a separate runtime.
- `empire_os/storm_contractor_review.py`: aggregates historical DFW cohort + dated first-party website observations + bounded same-domain public market signals; deduplicates and weights only research relevance. Capacity claims receive zero points, and model scores never confer outbound authority.
- `scripts/refresh_contractor_revenue_review.py`: a **one-shot command**, NOT a timer, writes an owner-readable (mode 0600) JSON snapshot only when explicitly invoked with `--write`. Without the flag it only prints non-sensitive summaries.
- `runtime/revenue_strike/contractor_founder_review_latest.json`: one evidence snapshot under the existing Revenue Strike runtime location. No contact information, contract PDFs, SMTP credentials, personal data or provider signing links.
- `empire_os/founder_dashboard.py`: adds a safe aggregate `contractor_revenue_strike` block to the *existing* founder overview. It exposes counts/status only, never prospect-level contacts or internals. The API's standard auth posture is unchanged.
- All binding agreements route through `/v1/deal-room` and the existing Documenso integration, not another signing service. They are currently marked `NOT_CREATED`.

## Work remaining before first legal outreach or paid pilot

1. **Independent identity**: corroborate companies and actual domain control; retain changed-identity quarantine. Distinguish Texas state-wide roofing licensure from local permit/registration requirements; separate from regulated public adjusting.
2. **Real B2B need**: obtain current evidence that a contractor wants/needs growth or territory intelligence, including decision-maker and service capacity. Hiring and claimed capacity are *research relevance only*.
3. **Product terms**: confirm an actual EmpireOS priced product and fulfilment capacity. The proposed $1,500/14-day entry pilot is a *hypothesis*, not a binding quote, discount approval or verified return.
4. **Consent and suppression**: inspect canonical EmpireDB prior contact/suppression and require a verified owned professional mailbox and founder authorisation for every outbound act. No silent send through Gmail, Resend or AWS.
5. **Contracting**: legal/founder-reviewed immutable PDF, Documenso signatures and independent signed-PDF/audit verification. Binding terms are NOT created by a review score.
6. **Payment and delivery**: verified USDT BSC payment and fulfilled deliverables; recognized revenue remains zero unless genuine payment/fulfilment evidence proves otherwise.

## Read-only repeat / snapshot reproduction

```sh
cd /srv/empire_os
PYTHONPATH=. ./.venv/bin/python scripts/refresh_contractor_revenue_review.py --as-of 2026-10-09
# To update the existing OBSERVE snapshot only:
PYTHONPATH=. ./.venv/bin/python scripts/refresh_contractor_revenue_review.py --as-of 2026-10-09 --write
```

No agents sent outbound, accessed private claims, signed documents, started services, changed DB rows, incurred paid traffic or issued a fee in this implementation.


## Third-party identity and canonical contact-history upgrade — 2026-10-09

The same existing Revenue Strike review now ingests the manually reviewed
`docs/DFW_CONTRACTOR_INDEPENDENT_EVIDENCE_20261009.json` with
`empire_os/storm_contractor_independent_evidence.py` as a pure corroboration
overlay. Direct BBB profile website links validate **directory website/name
matching**, not state incorporation, corporate-control, buyer intent or
consent to outreach:

- Max Exteriors: https://www.bbb.org/us/tx/desoto/profile/roofing-contractors/max-exteriors-llc-0875-91051523
- 180 Roofing: https://www.bbb.org/us/tx/mesquite/profile/roofing-contractors/180-roofing-contracting-llc-0875-90938685
- SPC Construction & Roofing: https://www.bbb.org/us/tx/euless/profile/roofing-contractors/spc-construction-roofing-inc-0825-155405122

**Holds:** RISE similar-name BBB profile links a different domain,
https://www.bbb.org/us/tx/southlake/profile/roof-structure/rise-roofing-construction-0825-1000215721 ;
Top Notch same-name BBB profile shows business age/rating inconsistent with
the reviewed prospect website, and does not establish the same domain,
https://www.bbb.org/us/tx/wylie/profile/residential-roofing/top-notch-roofing-restoration-0875-91348579 .
Mastercraft historical domain already has a different-company redirect hold.
Do not infer that any conflicting company is the same legal entity.

**Existing canonical prior contact reader reused** from
`scripts/materialize_company_routed_buyer_review.py` via optional
`--check-contact-history` in the existing
`scripts/refresh_contractor_revenue_review.py`. This is an opt-in, bounded
**read-only** EmpireDB check and requires the existing operational
`EMPIREDB_DSN`. Failed checks do not overwrite the prior review snapshot.
A negative company-domain match NEVER clears individual recipient suppression
or confers authority to email anyone. No separate database, service, timer
or CRM has been created.

Run with the existing authorised read-only EmpireDB service environment:

```sh
PYTHONPATH=. ./.venv/bin/python scripts/refresh_contractor_revenue_review.py --as-of 2026-10-09 --check-contact-history
```

A separate explicit `--write` is required to persist the OBSERVE-only
review snapshot. If the DB role/env is unavailable, this fails closed
instead of claiming that suppression has passed.

**Ranking is for research time allocation only.** $1,500 pilot fee and 14
days remain hypothetical. Active commercial need, confirmed person-bound
contact route, exact recipient suppression, founder send approval,
Documenso contract issuance, valid USDT BSC payment and fulfilled outcomes
all remain unverified.

## Existing relationship registry reconciliation (10 October 2026)

To avoid starting another CRM or forgetting conversations, the existing
`scripts/refresh_contractor_revenue_review.py` now directly consumes
`runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json`
through `empire_os/storm_contractor_relationships.py`. The join is exact
company domain, read-only and aggregate. Matched or ambiguous domain = HOLD
for review; *no match* = **not sufficient to assert zero prior contact** and
never a release for outreach. The join does not return email addresses,
thread IDs or the unrelated buyer CRM's private correspondence in contractor
snapshots. Gmail evidence is treated as untrusted historical context only.

10 Oct 2026 check: the source registry contained 185 relationships (4 two-way
relationships) and matched **zero of the eight contractor domains exactly**;
this is not a canonical suppression check, company registration, or interest
confirmation. The full source registry remains in its existing directory; no
second relationship registry or campaign list was created. The founder
overview shows only summary counts and read-only state.

Official public state identity-verification sources, where actual entity
results are not yet obtained:
- Free Texas Comptroller taxable-entity-status search by official name:
  https://comptroller.texas.gov/taxes/franchise/account-status/search.php
- Texas Secretary of State **SOSPortal** now handles official business filings
  and searches (modernisation launched 29 September 2026):
  https://www.sos.texas.gov/corp/business-law.shtml
- SOSPortal currently states a $1 search fee; **no fee or filing was executed**.
  https://www.sos.state.tx.us/corp/sosda/index.shtml
- A BBB listing, a sales-hiring listing, and self-published capacity claims
  are context for qualification, not official legal entity or ownership proof.

Regulated insurance claims/settlement percentage terms remain prohibited in
the default fixed-fee contractor-growth offer without counsel-approved scope
and appropriate licensing. In particular, no claims adjusting or percentage
of settlement services are implied.

**Revenue checkpoint:** Top candidates Max Exteriors, 180 Roofing and SPC
have directory-to-site name/domain corroboration and require official
registration and authorised buyer-contact evidence. PowerEdge remains a
research lead based on first-party hiring/context. No verified decision-maker
conversation, no approved send, no Documenso envelope, no paid order, and
no realised revenue from this cohort.

## Publicly listed company principals and bounded identity gate — 2026-10-10

This is a refinement to the **existing** independent-source records, not
CRM contact creation and not permission to send or sign:

| Research company | Directory-listed person | Listed business capacity | Source |
| --- | --- | --- | --- |
| Max Exteriors LLC | Pedro Torres | Owner/Director | https://www.bbb.org/us/tx/desoto/profile/roofing-contractors/max-exteriors-llc-0875-91051523 |
| 180 Roofing & Contracting LLC | Sebastian L. Ventura | Owner/Manager | https://www.bbb.org/us/tx/mesquite/profile/roofing-contractors/180-roofing-contracting-llc-0875-90938685 |
| SPC Construction & Roofing Inc | Jonathan Shaw | President | https://www.bbb.org/us/tx/euless/profile/roofing-contractors/spc-construction-roofing-inc-0825-155405122 |

These are professional name/role *directory statements*, not independently
verified identity, current spending authority, correct point of contact,
public email-route verification, or buyer interest. The existing
`storm_contractor_independent_evidence` parser checks that any listed
business principal is bound to the EXACT same source page and cannot
smuggle contact, budget, identity, suppression or outbound approvals.

Account-specific research question for founder-approved discovery:
- **Max:** What can Empire improve beyond the company's already visible
  digital customer funnel? Never claim a missing funnel or unverified ROI.
- **180:** Is the company seeking incremental commercial roofing or
  restoration opportunity in a territory it currently serves? No capacity
  claim absent a conversation. Investigate an alternate website mentioned
  on a similar-name social profile before treating it as canonical identity.
- **SPC:** Can its existing residential/commercial portfolio benefit from
  independently verified territory/permit/storm intelligence? This is an
  offer hypothesis, not a qualified buying need.

The direct `psql` checks from the ordinary Ubuntu runtime were blocked:
the local socket does not recognize the `ubuntu` database role and the
read-only CRM network role requires a password. This is expected role
separation, **not proof the EmpireDB guard ran**. The read-only command
`scripts/refresh_contractor_revenue_review.py --check-contact-history`
remains blocked until an existing authorized operational runner supplies
the canonical DB connection. Never copy credentials to a public endpoint
or Git repository and never disable suppression to get these leads sent.

Formal entity registration and named-recipient suppression are still
mandatory to progress these prospects beyond `CORROBORATION_PENDING`.

## Existing authorised EmpireDB reader reuse — 10 October 2026

The already-installed `empire-company-routed-buyer-review.service` (an
existing **oneshot** service, not a new timer or agent) has
`EnvironmentFile=/etc/empiredb.env`, `NoNewPrivileges=true`,
`ProtectSystem=strict`, and `ReadWritePaths=/srv/empire_os/runtime`.
Its last observed run used the canonical contact-history read successfully
(`history_guard_ok=true` in the separate company-routed review snapshot).
Ordinary shells cannot read the same DB credentials, which is expected and
does not justify exposing or copying them.

The service-owned script
`scripts/materialize_company_routed_buyer_review.py` now reuses **the
already-read, read-only** EmpireDB `prior_contact_domains` and
`suppressed_emails` sets once, after its existing buyer-review result is
safely written. It calls the existing Revenue Strike's deterministic
`run()` review and `attach_existing_canonical_contact_history()`
function and persists with that lane's **existing atomic private snapshot
writer**. No additional query, privileged role, service, cron timer,
SMTP call, Documenso API, CRM mutation, network send, or payment.
The contractor record receives a timestamp
`canonical_domain_history_read_at` only on successful canonical
readback. It includes *domain-level holds* and **never** marks a recipient
or outbound route as cleared.

A failed DB read prevents contractor evaluation; a failed contractor
review preserves the existing buyer-review result but reports a blocked
contractor status rather than fabricated success. Existing consumer
suppression, consent and human/founder approvals remain mandatory at the
actual recipient level before any send.

Runtime activation proof requires an actual authorised run of the
*existing* `empire-company-routed-buyer-review.service`; passing tests
alone does **not** prove the new snapshot has been refreshed with canonical
history. No unit file modifications or service restart are required.

## Official Texas Comptroller government open-data check — 2026-10-10

Read-only queries to the **original Texas Comptroller of Public Accounts**
public dataset, without a new service, credential, signup, fee or scraper
provider:

- Source: https://data.texas.gov/dataset/Active-Franchise-Taxpayers/9cir-efmm
- Official JSON endpoint: https://data.texas.gov/resource/9cir-efmm.json
- Dataset update reported by portal: **3 October 2026**
- Captured research: `docs/DFW_CONTRACTOR_TEXAS_PUBLIC_ENTITY_RESEARCH_20261010.json`

Three exact normalized legal-name candidates were found in the source:

| Company website under investigation | Official dataset legal name | SOS file | Raw right-to-transact code | Raw SOS code | Research action |
| --- | --- | --- | --- | --- | --- |
| maxexteriors.com | MAX EXTERIORS LLC | 0803161730 | A | R | Live entity/status and domain control confirmation still required; broad search found 2 other differently named Max Exteriors firms |
| spcroofs.com | SPC CONSTRUCTION AND ROOFING, INC. | 0801673144 | A | A | Live entity/status and domain control confirmation still required |
| 180roofing.com | 180 ROOFING AND CONTRACTING, LLC | 0803007394 | **N** | R | **OFFICIAL_STATE_CODE_REVIEW_HOLD**, zero research priority, do not contact pending a direct official account-status verification |

The raw code **N** is not interpreted as an official revocation/forfeiture
finding without independent, current, primary-source detail verification.
The code difference from **A** is sufficient reason for a conservative
hold. The public open-data extract is **not** a certificate of fact/status
or proof that a state legal entity controls the candidate domain. Registered
agent, authority of the named business person, legal ability to perform
claims-adjacent services, marketing purchase intent and recipient-level
suppression remain unverified.

For the current legal status, use the official live Comptroller entity search
by the above filing number:
https://comptroller.texas.gov/taxes/franchise/account-status/search
and, if needed, Texas SOSPortal formal entity filing records. Avoid inferring
legal capacity from generic third-party directory results.

## CRM reconciliation truth — changed on 10 October 2026

The existing commercial relationship registry was independently refreshed
and grew to **195** company records. Seven of the eight DFW contractor
domains now exist as **research-only** company records, with **no recorded
inbound/outbound or linked Gmail conversations** in those seven records.
The existing relationship join now distinguishes:

- `existing_relationship_domain_matches`: deduplicated existing CRM
  company records, including research-only
- `existing_research_only_domain_matches`: no actual correspondence in
  registry (current seven)
- `existing_conversation_domain_matches`: actual registry-backed
  correspondence evidence (current zero)

No source record is promoted to a prior-customer or approved-outbound state
merely by appearing in a research inventory. A negative contact history,
a positive public business record, or a directory-listed manager are not
recipient-level suppression clearance and are never an instruction to send.

**Revenue stage remains zero verified buyer conversations and zero
recognised revenue from the DFW contractor cohort.**

## Existing rapport-first outbound guardrail reused — 10 Oct 2026

Per founder instruction, **building rapport comes first**. The existing
`empire_os.outbound_department.plan_outbound_account`, implementing
`rapport_first_human_specific_v1`, remains the **only source of outbound
relationship-stage policy**. No duplicate contractor-specific copy-policy
engine, new customer table or mailbox has been introduced.

The DFW contractor review now invokes that existing planner only with the
facts it actually has: an as-yet-unverified company-bound identity,
no established person-bound decision-maker contact, no confirmed buyer
review and no outbound evidence. The bounded read-only review of all
eight contractors therefore returns `RESEARCH`, with
`first_touch_cta_allowed=false`, `commercial_pricing_allowed=false`,
and `execution_authority=none`.

That policy's actual progression is from verified identity and an
evidence-backed first **rapport** draft, to value and nurturing, to an
appropriate soft conversation opener only after sufficient observed
value-touch history, and to a closer only with a canonical qualifying
commercial reply or commercial-ready state. Unclassified, negative,
later, wrong-person and unsubscribe replies have distinct holds.

A product being commercially approved in the existing catalog does
**not** authorize a first-touch pitch. The existing catalog contains
`managed_service` — Empire Opportunity Intelligence Pilot — at
$1,500 flat, active, founder-approved, and binding-terms-ready
(according to the catalog snapshot). This is a possible product
**only if** a properly qualified contractor later opts into reviewing
commercial terms. The DFW $1,500/14-day scope is still an internal
pilot hypothesis, **not** a binding quote or guarantee.

### SPC company alias and historical contact caveat

The public business contact observations are captured in
`docs/DFW_CONTRACTOR_BUSINESS_CONTACT_RESEARCH_20261010.json`.
SPC's own website publicly lists `info@spcgc.com`; a City of Bedford
historic contractor register also lists `jshaw@spcgc.com` with
registration expiry 2025-04-04. That register does not verify that
the named business person still uses that email or that the business's
registration is currently active. Neither email has been validated
by sending or marked approved. The public general inbox is
**company-routed, never person-bound**.

The existing canonical read-only history evaluator now includes
`spcgc.com` as an additional company-associated domain for
`spcroofs.com`, and conservatively blocks for any historical
outbound or suppression match on **either** domain. It separately
reports exact suppression matches for the first-party public generic
business email and historically printed person email, but a
*negative match* does not clear an address. There is still no
`recipient_suppression_verified` or `outbound_authorized` state.

**No outbound copy, send, scheduling, contract or payment is generated
by this new research evidence.** Any draft must eventually go
through the **existing** Outbound Department copy validator and
independent send-authority checks.

### UK evidence calendar vs UTC service-run date (10 October 2026)

A live `empire-company-routed-buyer-review.service` one-shot at
2026-10-09T23:46:37Z returned `contractor_history_state=BLOCKED_ValueError`
while its canonical DB reader reported `history_guard_ok=true`. The
source observation date of the new 10 Oct 2026 business-contact review was
ahead of the worker's still-9-Oct UTC calendar date. **No unsafe
overwrite occurred**; the preceding canonical contractor snapshot stayed
intact.

The existing runner now calculates the report `as_of` date explicitly in
the founder's `Europe/London` timezone, while retaining the authoritative
database access and snapshot-read timestamp in UTC. This resolves the
UTC/UK midnight observation-boundary case without weakening freshness
checks, moving any data or granting outbound authority. Dedicated
boundary tests cover 2026-10-09T23:46Z (10 Oct in London) and naive-time
rejection. Live one-shot readback is still required after this fix.

## Canonical $1,500 product reference — 10 Oct 2026

The existing commercial catalog at
`runtime/commercial_catalog/latest.json` contains exactly one matching
`managed_service` row: **Empire Opportunity Intelligence Pilot**,
product ID `a4b11ace-4199-4419-a43d-2bcbeda33364`. Its current
founder-approved internal price is **USD 1,500 flat**, with verified
catalog/version/pricing state and an original approval reference
`founder_approval:first_cash_economics:2026-09-21`. The existing
`commercial_pricing_live_verifier.verify_catalog_snapshot` independently
checks price drift in the same source; no second catalog or quote engine
was created.

`scripts/refresh_contractor_revenue_review.py` now attaches a strictly
**internal** product reference if the catalog is a bounded, fresh,
unambiguous, founder-approved snapshot and its existing price verifier
passes. A missing, stale, duplicated, mismatched, drifted or otherwise
invalid product remains an explicit hold. A currently catalog-approved
product is **not** a recipient-specific purchase recommendation, a
completed price quote, agreed 14-day scope, verified fulfilment, or
permission to include pricing or a CTA in a first touch. The existing
rapport policy continues returning `RESEARCH` for all eight candidates.

The public-facing read-only founder summary reports only the count of
verified internal products, **not** private catalog pricing, contact data,
or prospect-specific commercial terms. Later governed deal work must use
the existing Deal Room + Documenso after demonstrated two-way interest,
recipient checks, and founder approval. No call, email, contract,
payment, or recognised revenue results from this catalog link.

### Actual service proof of rapport-first refresh

The authorised one-shot `empire-company-routed-buyer-review.service`
reported `Result=success`, and the private 0600 founder snapshot at
`runtime/revenue_strike/contractor_founder_review_latest.json` shows
`as_of=2026-10-10`,
`canonical_domain_history_observed=true`,
`rapport_gate_research_count=8`,
`public_business_email_research_count=1`,
`outbound_authorized=false`.
The actual loopback founder HTTP endpoint
`GET http://127.0.0.1:8766/v1/founder-dashboard/overview` returned
HTTP 200 with the same rapport/candidate/hold counts. The internal
catalog-linked extension needs its **own subsequent service-run
readback** before claiming that specific new field is production live.
