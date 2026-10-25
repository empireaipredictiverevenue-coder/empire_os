# Empire AI — PR / Editorial / Consultancy / Proposals integrated review (25 October 2026)

## Original systems and conservation rules

This bridge is an **on-demand, isolated REVIEW_ONLY stage**. No second CRM, database, publisher, scheduler, model, bot, or acquisition department. Its review packet draws from:

- The original PR/consultancy worktree on `agent/pr-consultancy-review-20261011`: exact Gmail sent receipts (two historical sends), publisher contact research, founder-approved three-price policy and the existing held contracts/intake evidence.
- The canonical Marketing & Growth `GROWTH_001` editorial pitches and AI-readiness original draft: independent editorial decisions and retained rights checks.
- The existing native buyer proposal handoff and existing tender consultant's founder handoff: internal review, not binding bids or sales.
- The existing Revenue Distribution snapshot in `runtime/revenue_distribution/latest.json` when passed as `--distribution-root`: **commercial traffic-supply inventory, not proof of independent PR placements**.

The snapshot has separate `pr`, `editorial`, `consultancy` and `proposal` lanes; stable review item IDs, hashes for all read evidence, and empty canonical CRM binding fields. Historical Gmail threads are linked by the **existing message-provider thread ID**, not fictitious CRM identities. The two recorded prior PR sends take precedence over older contact research saying `pitch_sent=false`; prevent duplicate pitching. New editorial submissions, journalist responses, qualified buyers, proposal acceptances, delivered contracts, payments and earned backlinks are **never inferred**.

## Current runnable stage

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_advisory_bridge_20261025 \
  --review-only \
  --repo-root "$PWD" \
  --pr-root /home/ubuntu/empire_agents/empire_pr_consultancy_20261011 \
  --distribution-root /srv/empire_os
```

No write flags. The packet goes to stdout only, so it is not exposed on a public website or stored in a second ledger. Tests: `PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -m pytest -q tests/test_earned_media_advisory_bridge_20261025.py`.

## Proposed future connections — not falsely marked live

1. Existing Founder Console review desk consumes this reviewed packet through the original authenticated departmental read route (requires maintainer approval and tenant/auth verification).
2. Existing canonical Smart CRM links a record **only after** an exact company/person/tenant identity, verified existing thread, consent/suppression and legitimate source mapping are proven; link existing IDs, no broad CRM ingest.
3. Existing Marketing & Growth owner handles editorial rights/factual acceptance and ASTRA publisher. Journalist/PR pitches stay independent of consultancy CTAs and cannot demand backlinks.
4. Existing customer sales owner uses the approved pricing as starting points, while scopes/costs/terms are held; existing governed buyer outreach handles exact send approvals and deduplication. No outbound release inherited from the bridge.
5. Existing payment/settlement evidence reconciles independently before realised revenue is reported. Do not turn a citation, enquiry, unsigned proposal or forecast into booked income.

## Limits

The original PR receipts date to 11 October: provider SENT labels are not delivery or replies. The canonical Revenue Distribution snapshot was from earlier October and is historical. No live Gmail query, EmpireDB query, live current SEO ranks, live third-party editorial placement checks or production CRM sync is performed by this stage. Existing `/commercial` enquiry policy and CRM authentication must be read back separately before any private console or external workflow activation.

## Existing Marketing / SEO department integration (isolated branch only)

The existing `scripts/review_seo_department_integrated_20261018.py` now accepts optional flags `--earned-media-advisory`, `--earned-media-pr-root` and `--earned-media-distribution-root`, returning the new `earned_media_advisory` section within its existing read-only response. On 25 October this optional combined invocation returned 4 PR, 3 editorial, 4 consultancy and 1 proposal review items; the parent SEO department separately returned `HELD_UNVERIFIED_DEPENDENCY`. Neither result authorises publishing or CRM changes.

A fresh read of the two exact original Gmail threads on 25 October found one SENT message in each and no reply in either thread. This is not a full mailbox search, delivery confirmation, or proof an editor saw the message. Two other PR outlets remain research candidates, not approved next sends.

QA: 67 relevant bridge/SEO/editorial regression tests passed. Isolated branch integration is source-staged and has not been merged into `/srv/empire_os`; active production continues without a new runtime, schedule or endpoint. Existing founder authentication and canonical CRM matching are separate gates for an approved future private console release.

## Stage 2: internal Founder API and CRM match preview

- New router `empire_os/founder_earned_media_api.py` is mounted in the existing loopback Founder service under GET `/v1/founder-earned-media/review`, with `EMPIRE_EARNED_MEDIA_FOUNDER_READ_ENABLED` disabled by default. No canonical reads or writes, outbound or publication.
- Staged founder UI at `apps/search-command-centre/src/app/founder/earned-media/page.tsx` is 404 unless `EMPIRE_EARNED_MEDIA_FOUNDER_UI_ENABLED=1` and `EMPIRE_FOUNDER_CONSOLE_PRIVATE_AUTH_VERIFIED=1`. Those flags are **not authentication**; they must not be enabled or the change deployed until existing founder ingress/session authority is independently proven. There is no new public main-site link.
- `empire_os/earned_media_crm_match_preview.py` is an in-memory exact-join classifier, with no EmpireDB driver. It accepts separately owner-validated canonical tenant/company/prospect/opportunity identifiers and a reconciled original Gmail thread. Mismatched tenants, partial proofs, unknown sources or conflicting matches remain held. Even one apparent match is only a candidate requiring owner review, not permission to write Smart CRM.
- Two original press threads remain historical receipts, not fresh Gmail observations. No automatic follow-ups, scheduler, new agents, sales pipeline writes, revenue attribution or deployment.

## Stage 3: lead-generation and revenue qualification — read-only

**Implemented in the same isolated branch:** `empire_os/earned_media_leadgen_review.py`. CLI can now append the source-scoped lead-generation review by adding `--with-leadgen` to `scripts.review_earned_media_advisory_bridge_20261025`. The disabled-by-default existing Founder API view also attaches the same read-only summary and the hidden Founder UI offers a researched-prospect worklist.

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_advisory_bridge_20261025 \
  --review-only --with-leadgen \
  --pr-root /home/ubuntu/empire_agents/empire_pr_consultancy_20261011 \
  --distribution-root /srv/empire_os
```

### Source evidence and actual 25 October test result

1. `docs/commercial/SAAS_DIRECT_BUYER_REQUESTS_20261024.md` supplied **three research observations**, including two Upwork-indexed direct B2B RevOps/HubSpot external service requests and one unverified brokered dashboard opportunity. URLs must exactly match the stored research file; each listing still requires independent fresh availability, marketplace entitlement, buyer identity and delivery-capability verification. **No paid Connects, impersonation, platform-bypassing outreach or fabricated experience**.
2. Existing `/srv/empire_os/runtime/revenue_distribution/latest.json` supplied **20 named organisation research rows**, with eight existing UUID-shaped canonical prospect references and twelve without. The latter are preserved as **UNBOUND research**, not discarded or invented CRM IDs. Even rows with prior verified company contact metadata do not demonstrate buyer intent or permission to send.
3. All sources are immutable within one review call: the Revenue Distribution file hash must equal the digest captured by the original bridge. Any changed source between stages returns HOLD. No network, direct CRM query, new scraper, new database, scheduler, public page, external email or payment was invoked.
4. First real-source output: **23 candidate observations total = 3 public service-demand signals + 20 researched accounts; zero verified qualified buyers, zero accepted offers, zero paid customers**. All are review items, not a live buyer pipeline. The reviewer does not expose emails from the research queue.

### Multi-sector commercial routes

| Evidence source | Potential value-first output | Offer hypothesis | Release blocker |
|---|---|---|---|
| Publicly indexed B2B RevOps / HubSpot scope | Original MQL/SQL + funnel audit checklist | Founder-led £2,500 Opportunity Assessment | Listing state, portal costs, experience, scope and buyer not verified |
| ERP / forecast decision-support request | Original one-page data lineage/forecast model | Narrow consulting assessment if client wants it | Specialist ERP integration not verified; cannot quote full implementation |
| Brokerage-sourced property operations dashboard | KPI checklist for internal review | Only after real host and buyer identified | Original post and actual supplier brief unverified |
| Eight canonical enterprise research prospects | Source-linked, company-specific free insight summary | Strategic advisory/Blueprint only after proven need | Buyer intent, fresh contacts, suppression, capacity and terms |
| Twelve unbound home-services research organisations | Review company/source and potential operational data gaps | No offer until genuine problem/identity | Canonical prospect identity missing |
| Existing PR and editorial relationships | Original expert commentary, placements if accepted, qualified first-party enquiries | Own brand attention → transparent consultancy enquiry | Publisher independence, placement, attribution, voluntary enquiry |

The three founder-approved consultancy list prices are a **policy**, not quotes or recognised revenue. Conditional `£10k` arithmetic shows four £2,500 assessments or one £7,500 blueprint plus one £2,500 assessment, if all separate contracts and payments were real. £3,000/month advisory requires capacity and terms approval. These examples are *not forecasts*; cost estimates, actual pipeline value, probabilities, settled cash and fulfilment have not been verified.

### Next real commercial milestones

- **Fresh signal:** reconfirm a live external request or independent business problem with a genuine buying need. Record original dated source and rights; do not promote a job ad or a research score into a signed service enquiry.
- **Value first:** prepare one helpful original, source-linked sample suitable for a specific buyer; do not misrepresent the sample as delivered client work or spam a pitch. Use existing founder-reviewed outbound authority and mail history if a lawful, appropriate business contact is proven.
- **Exact Smart CRM:** existing immutable prospect ID, authenticated tenant, current permission/suppression evidence, original conversation and a real source-linked reply. Unbound companies cannot bypass this step.
- **Commercial next step:** the founder scopes a suitable £2,500 assessment or negotiated blueprint/advisory, verifies costs and ability to deliver, obtains accepted written terms and actual payment. All contracting/settlement stays in the original existing finance loop.
- **Attribution:** PR accepted third-party placement or an original published website page must have real URL evidence; record independently measured site traffic, opted-in enquiries, accepted proposal, settlement and delivery separately. Link first-party source identifiers into existing SEO/GSC and CRM only once verified, never manufacture backlinks/AI citations.

**Prohibited shortcuts:** no paid traffic/editorial, mass unsolicited email, duplicate PR pitches, silent data transfer to outside parties, unverifiable delivery claims, implicit CRM import, settlement guesses or automatic contracting. Mode remains OBSERVE. No production deployment or public route enablement.


## Stage 4: founder value-first sales assets and usable review CLI (25 October 2026)

The original 23 observations remain 23 research items, **not 23 qualified leads**. Two Upwork indexed scopes are stronger *external demand signal* examples for validation, but are not currently supported as executable bids: founder account eligibility, possible paid Connects, original listing availability, true buyer identity, competing bidders and demonstrable HubSpot implementation experience must all be checked independently. The engine has not accessed those buyer accounts or messaged anyone.

**Implemented:**

- `empire_os/earned_media_value_first.py`: deterministic read-only previews from exact existing lead opportunity IDs. Three source-specific original samples cover lifecycle forecasting, ERP-to-CRM lineage and generic KPI dashboard questions. Research companies receive a hypothesis-only short brief and an explicit original-source fact-check. No templates contain invented buyer pain, case studies, outcomes, ROI, personal email or platform implementation claims.
- `GET /v1/founder-earned-media/lead-opportunity/{opportunity_id}/sample` on the **existing** Founder read service; mounted, disabled by default, with no POST/PUT/DELETE routes. Unknown/ambiguous IDs return 404; held source returns 503. No new agent, database, scheduled task, external SaaS or public campaign.
- `/founder/earned-media/sample/[opportunityId]` staged Next.js page, linked from founder research cards, still requiring both `EMPIRE_EARNED_MEDIA_FOUNDER_UI_ENABLED` and `EMPIRE_FOUNDER_CONSOLE_PRIVATE_AUTH_VERIFIED`. Flags are NOT authentication, and **must not be enabled or deployed before the founder ingress/session and tenancy have been verified**.
- CLI `--summary` presents brief source health, original PR sent/not reply-verified count, lane counts, lead counts, top-five founder actions and no-sales truth, instead of the full multi-thousand-line JSON packet. CLI `--sample-opportunity-id <leadreview_...>` outputs one original sample packet. A held upstream research source returns exit 2 instead of reporting successful readiness. The default output remains unchanged.

**Compact founder review:**

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_advisory_bridge_20261025 \
  --review-only --with-leadgen --summary \
  --pr-root /home/ubuntu/empire_agents/empire_pr_consultancy_20261011 \
  --distribution-root /srv/empire_os
```

**Preview the strongest direct external service-request sample, without submitting a bid:**

```bash
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_advisory_bridge_20261025 \
  --review-only --with-leadgen \
  --sample-opportunity-id leadreview_bc38f53c69a3b9cfabdead8e \
  --pr-root /home/ubuntu/empire_agents/empire_pr_consultancy_20261011 \
  --distribution-root /srv/empire_os
```

All sample previews are internal drafts; sending, publishing, quoting, committing to vendor terms, CRM updates, finance, KYC and production activation remain gated. Underlying source observations are historical and their existence does not establish fresh marketplace eligibility or source credibility. The next source-of-truth milestones are current independent buyer need, real contact permission / portal eligibility, deliverable scoping and qualified inbound replies, with payments and realised revenue recorded only through existing EmpireDB settlement evidence.


## Stage 5: independent sales-actionability barrier (25 October 2026)

**Problem addressed:** a research priority of 70/100 never meant an actual sale could be pursued. Previously, the operator could still confuse discoverable public requirements, researched company identities and a ready-to-send CRM lead. The new component `empire_os/earned_media_sales_actionability.py` classifies each source observation into a **held commercial readiness lane** and lists evidence required before independent founder actions.

**Real source review (public web, 25 October 2026):** Exact original Upwork pages for both RevOps/HubSpot external consultancy requests were discoverable in web search. The first also appeared in the platform's HubSpot-category index. Both displayed 50+ proposals. Search-index presence proves neither authenticated application availability nor UK founder account eligibility, free Connects, buyer identity, sufficient professional qualifications, project fit, or any willingness to buy a narrower £2,500 consultancy audit. The public observations are recorded as a **dated, degradable research artefact** in `docs/commercial/PR_CONSULTANCY_MARKETPLACE_PUBLIC_OBSERVATION_20261025.json`. They cannot be elevated to a live buyer check, and become STALE after the conservative source window; invalid, duplicated, future-dated, or attempted self-authorising records are downgraded/held.

**Executed read-only count:** 23 historical observations, partitioned into:
- **2** marketplace consultancy demand signals: `HOLD_MARKETPLACE_ELIGIBILITY_AND_DELIVERY`.
- **1** brokered dashboard listing: `HOLD_BROKERED_BUYER_ORIGINAL_SOURCE`.
- **8** existing canonical research prospects: `RESEARCH_ONLY_CANONICAL_ID_NOT_BUYER_INTENT`.
- **12** unbound researched companies: `RESEARCH_ONLY_COMPANY_IDENTITY_UNBOUND`.

**Zero** independently qualified buyers, permitted new contacts, approved proposals, accepted clients, verified settlements, or realised revenue. The staged Founder Console and `--summary` now display these counts and the exact next evidence step. Two PR sends remain historical, reply unverified.

**Controlled upgrade:** The source reader attaches evidence provenance (digest, historical date and freshness), executes no live network or CRM query, does not unlock a sales action even if the search result is fresh, checks exact URL-ID pairing, and refuses any record claiming unsupported commercial authority. If upstream source reconciliation is held, actionability holds too. No additional bot, messaging integration, scheduling process or transaction path has been created.

**First-party alternative already built elsewhere in EmpireOS:** `/predictive-revenue` contains the Revenue Leakage Guide and nonbinding interest intake; `/commercial#commercial-enquiry` contains a consent-specific enquiry form. Reuse these, not a parallel lead-capture database or a duplicate sales funnel. PR/editorial can attract organic, unpaid attention, but publication or distribution is a separate governed action and a published article is not proof of measured enquiry.

**Operator:** run the previously documented `--review-only --with-leadgen --summary` command. Look for `sales_actionability_counts`, `eligible_for_contact=0`, `eligible_for_proposal=0` and the source-observation state. The next commercial action is to independently confirm an actual buyer problem and contact eligibility or to receive an opted-in first-party enquiry, then reconcile current suppression, tenant authority and capacity; any individual proposal or funds remain separately authorised.

**Deploy:** isolated worktree only. Do not turn on private Founder route flags or merge into production without verified private ingress and explicit release approval.


## Stage 6 — Original owned guide to existing consented enquiry (25 Oct 2026)

**Objective:** Improve the actual conversion connection without creating a second funnel, database, tracking pixel, paid editorial distribution, or unverifiable buyer records.

### Implemented only in `agent/earned-media-advisory-bridge-20261025` (NOT PRODUCTION)

- Existing original `SaaSRevenueLeakageGuide` attached to `/predictive-revenue` now calls `ownedRevenueGuideProposalHref()`. The exact staged link is `/commercial?entry=%2Fpredictive-revenue#commercial-enquiry`. The buyer stays on the **existing consent-specific commercial form**, with existing dynamic catalog verification and idempotent retry identity. No cookies or visitor analytics were introduced.
- The `entry` parameter is accepted only as an exact, bounded browser-claimed source, never as a verified Google click, publisher conversion, opted-in buyer, or revenue. Existing `record_founder_led_interest` records the hint only when a real visitor specifically consents to an enquiry; nothing has been submitted by this worktree.
- The unimplemented `/insights/revenue-opportunity-assessment` path was present in the frontend/backend entry allowlists, but no matching Next.js page exists. It is removed from **both** allowlists in this staging branch, avoiding phantom source attribution. The original GROWTH-001 AI readiness article remains only a separate draft, not a public new route or a published editorial claim.
- Added `empire_os/earned_media_first_party_conversion.py` which compares the reviewed original article digest, draft-only brief, existing public guide/CTA, real route source, frontend/backend exact allowlist, and first-party form consent, no-autosend and unverified attribution semantics. It catches symlink/tamper, source authority drift, missing consent, missing artifacts and invalid source text.
- Existing `--review-only --with-leadgen --summary` and disabled-by-default Founder review now expose `owned_content_conversion_state`. This output is **source-code readiness only**; the real guide URL still needs verified production website-owner ingress/release, visits, attributable enquiries, accepted terms and bank-settled receipts before making revenue claims.
- Public site edits are **staged only**, requiring independent ASTRA/site-owner code review and a founder release decision. No deployed website, indexation submission, third-party editorial pitch or publisher placement was changed.
- The original `GROWTH_001_AI_READINESS_ARTICLE_BRIEF_20261016.json` explicitly has publication and new-page proposal authorization set to false; this release respects those holds.

### Verification sequence before deployment

1. Independent ASTRA review of this **existing page** CTA modification and contact-consent parity; verify exact website public ingress and private Founder session authentication before any merge/flag change.
2. Retest production `/predictive-revenue`, `/commercial`, offers GET and existing idempotent intake **without making a fabricated POST**.
3. After approved release, measure actual privacy-respecting page visits with approved first-party analytics, and reconcile any genuine, separately consented enquiry to existing EmpireDB prospect identity. A visitor-submitted entry hint remains a claim unless independently validated.
4. Human qualify requested scope and delivery, approve the exact proposal/terms separately; log verification of settlement and fulfilment in existing economic memory. Do not infer results or conversion rates from source code.

### Current proof and limitations

No real measured traffic, campaign buyer response, opt-in enquiry, company-qualified buyer, paid contract, bank settlement or ROI was verified during this change. This stage strengthens the **path that a willing buyer may follow**, not the count of buyers.

### Command

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_advisory_bridge_20261025 \
  --review-only --with-leadgen --summary \
  --pr-root /home/ubuntu/empire_agents/empire_pr_consultancy_20261011 \
  --distribution-root /srv/empire_os
```

Expected staging-only state: `owned_content_conversion_state=STAGED_EXISTING_GUIDE_TO_EXISTING_INTAKE_NOT_LIVE_VERIFIED`. Source clicks and real consented enquiries remain false or unknown.


## Stage 7: actual live GET-only release readiness, no production activation

**Live observation (25 Oct 2026, non-mutating existing original canary):**

- Existing `scripts.probe_first_party_sales_http_readonly --check-private-inbox` completed. Both current public commercial/predictive pages responded, **two** compiled intake endpoints were found, and current first-party catalogues reported **10** commercial offers and **5** Predictive Revenue products. Both existing CRM prospect/buyer APIs denied anonymous access, and private CRM health passed. These facts do **not** demonstrate that any staged new code is deployed, visitor consent was submitted, or a buyer reached Smart CRM.
- Loopback-only existing Founder Console `/founder` responded 200 **without founder credentials**. This is a local server-bound GET and does NOT determine whether Cloudflare/ingress protects public traffic. New `/founder/earned-media` and `/v1/founder-earned-media/review` responded **404** as the feature is off. **DO NOT enable the flags**, link the private page publicly, or claim external Founder authentication from this local observation.
- Existing first-party canonical acquisition counts and tenant-scoped customer rows were **not queried**. A visible public catalogue is not evidence of site conversion or settled revenue.

**New implementation:** `empire_os/earned_media_live_release_preflight.py` is a strictly read-only composer around the pre-existing, audited GET-only public canary and anonymous-CRM-denial canary. No duplicate fetch logic, no authentication bypass, cookies, CRM login, POST, invoice, database insert, mail send, published page, systemd unit or scheduler. It explicitly separates: staged source code, live pre-existing GET surface, anonymous CRM boundary, independent Founder ingress/session security, site-owner authorization, deployed new CTA, real buyer replies, contract and bank settlement. It ALWAYS returns `HELD_PRIVATE_AUTH_AND_PRODUCTION_RELEASE` until a separately approved verified release path exists; even a caller boolean claiming founder authentication cannot upgrade it.

**Optional operator command (must exit 2 because release remains held):**

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_advisory_bridge_20261025 \
  --review-only --with-leadgen --summary --live-release-preflight \
  --pr-root /home/ubuntu/empire_agents/empire_pr_consultancy_20261011 \
  --distribution-root /srv/empire_os
```

`--live-release-preflight` must be **explicitly requested** and is not invoked in the ordinary `--summary` or private Founder API read. The live results are compact and contain only booleans, source states and release holds. Tests inject GET-only fixtures and prove the existing canary was not called during ordinary review. The read-only check is not a real release operation.

**Relevant first-party skills applied:** `empire-lead-research` for dated source verification, provenance and deduplication; `empire-commercial-email-copy` for explicit blocking where contact/consent/suppression or deliverable evidence is missing. These skills are advisory, not authority to send.

### Required gate to move beyond staged evidence

Independently verify external authenticated Founder ingress AND real signed-in session scoping (not local 200 or an environment flag), ASTRA and founder's exact website diff approval, public GET/compiled new CTA after an authorised deploy, then genuine consented enquiries with canonical tenant/exact thread proof, individual scoped proposals and settled cash. Production website unchanged by this worktree, and no publication or outbound authorised.
