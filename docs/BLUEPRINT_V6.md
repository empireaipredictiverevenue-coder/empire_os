# Empire AI — Predictive Revenue OS Blueprint v6

Date: 2026-09-17
Status: CANONICAL CURRENT ROADMAP
Supersedes blueprint_v5.md for current architecture decisions. v5 is retained as history only.

## Mission
Build a governed Predictive Revenue operating system that detects commercial signals, predicts economics, creates demand, acquires and qualifies opportunities, matches buyers, closes revenue, verifies payment, measures profit, learns from outcomes, and reallocates resources through Astra.

## Build Principle
QUALITY → FIRST REVENUE → PROVE ECONOMICS → CAPTURE OUTCOMES → IMPROVE PREDICTIONS → AUTOMATE → SCALE.

## Canonical Architecture Decisions
- Truth/data plane: Supabase project `owbeinlfcfdtwcwrttjy` (Empire-AI Database). SQLite is legacy/cache only.
- Operating coordinator: Astra. Deterministic/local first; premium AI only when economically justified.
- Execution bus: remain OBSERVE until explicit promotion approval.
- Public domain: `empire-ai.co.uk` through Cloudflare Tunnel `Empire-AI`.
- Public gateway: read-only, governed, no settlement/allocation/activation mutation endpoints.
- Agent Web: WebMCP + MCP + A2A share one capability catalogue and governance model.
- Current payment rail: USDT on BNB Smart Chain. Solana/USDC/Phantom/Anchor settlement is retired from active architecture.
- Buyer/payment truth: only independently verified commercial evidence counts as actual revenue.
- Outbound: governed approvals, idempotency, DNC/opt-out/compliance controls.
- Voice: Vonage + ElevenLabs when Conversation OS phase activates.

## Current Live State
- Domain/tunnel restored and reboot-persistent.
- Public Agent Web health, A2A Agent Card and WebMCP manifest live.
- Canonical market intelligence snapshot is Supabase-backed and public-safe/aggregated.
- `market.search`, aggregate `opportunity.search`, and revenue-backed SEO keyword intelligence execute live.
- AEO/GEO/citation evidence adapter ✅ local/tested: only observed citation/mention evidence is counted, missing evidence remains unknown, and no fabricated visibility score or ranking is emitted. Production observation ingestion remains gated.
- Astra bootstrap is deterministic/plan-only.
- Autonomous execution service remains OBSERVE.
- BSC payment verification, buyer-payment evidence binding, and separated payment
  proposal/human-approval/verifier roles are deployed fail-closed in canonical Supabase.
- BSC smart-contract escrow database rail is deployed fail-closed; contract mainnet deployment remains gated by external review and production roles.
- Empire Intelligence Fabric schema is being built as the shared temporal/provenance graph across intelligence domains.
- Protected untracked `recovery/` and `toop` remain untouched.

## Cross-Phase Intelligence Fabric — ACTIVE FOUNDATION
The Empire Intelligence Fabric is the shared substrate beneath all intelligence domains. It is not a replacement roadmap phase and does not move the CURRENT marker away from Phase 3F.

Core graph objects:
- canonical companies and people; employment and buying roles; verified contact points
- provenance-backed temporal facts with first/last seen and validity windows
- market, buyer, intent, opportunity, revenue, competitive, pricing, search, AEO/GEO, conversation, risk and governance signals
- TAM segments for software/MRR, high-ticket, managed services, white-label, enterprise and escrow/payment fit
- versioned Omega/Astra scores with confidence, feature evidence and explanations
- offer-fit and expected-value scoring per company
- commercial outcomes for calibration, causal learning and future Digital Twin simulation

Operating rule: intelligence records remain intelligence until a governed qualification step promotes them into CRM/outbound. No crawler, score or model may self-create buyer activation, outreach or settlement.

Moat direction: temporal graph + source provenance + signal fusion + commercial outcomes + causal models + execution history. Every future intelligence engine must read/write through this shared substrate rather than create isolated data silos.

Competitive design target — business-web search plus closed-loop intelligence:
- crawl/index primary business websites directly at internet scale; retain source text and change history
- natural-language ICP, exact-phrase and domain-lookalike search across the company universe
- multilingual company discovery, technographics, domain health and open-web decision-maker discovery
- count-before-materialize queries, exclusions/suppression and confidence floors before CRM promotion
- agent-native API/MCP/SDK access, but all mutation remains governed
- exceed discovery-only platforms with temporal signal sequences, buying-committee reconstruction, multi-offer fit, expected deal value, next-best-action, payment/revenue truth, outcome-conditioned memory and causal learning
- learn from Empire-specific wins/losses/fulfilment/churn/revenue so ranking optimizes for probability of profitable Empire outcomes, not generic ICP similarity alone

## Phase Roadmap

### Phase 0 — Foundation ✅
EmpireOS core, canonical identity, Supabase truth, security controls, execution bus, observability, GitHub/deployment discipline, Cloudflare public gateway.

### Phase 1 — Signal + Acquisition ✅ / Expanding
Satellite Sniper, Storm Tracker, Warehouse Sniper, Market Scanner, Reddit/community intelligence, permits/weather/public data, Source Mesh, OpportunitySignal, entity resolution, quality/provenance, canonical prospect acquisition.

### Phase 2 — Commercial Control Plane ✅
Commercial products, buyer records/capacity, commercial events, fulfilment, idempotency, approval gates, buyer evidence, atomic allocation, activation gate, locked GTM RPCs.

### Phase 3 — First Revenue — IMPLEMENTATION FROZEN / PRODUCTION PROOF GATES CARRIED FORWARD
3A Qualification ✅
3B Market materialization ✅ mostly
3C Canonical acquisition ✅
3D Buyer matching/allocation ✅
3E Governed outbound ✅ implementation complete; production runtime/webhook activation gated
3F Outcome feedback ✅ implementation complete locally; production activation/revenue-proof gates carried forward

Phase 3 no longer blocks later engineering. Its remaining finish line is one genuine governed buyer → agreement → verified payment → delivery → outcome → recognized revenue loop. That proof remains mandatory before expanding consequential commercial authority, but Phase 4/5 may continue in OBSERVE/local-safe modes.
First-revenue proof readiness ✅ local/tested: `/v1/first-revenue/readiness/preview` now evaluates the exact evidence chain for verified buyer identity + terms + human approval + approved outbound intent + send/delivery + agreement + verified USDT/BSC payment + fulfilment + outcome + recognized revenue. It is preview-only and never sends, charges, fulfils or recognizes revenue itself.

Phase 3E deliverables:
- Buyer discovery from real businesses, not placeholder/public-data pseudo-buyers. Canonical buyer discovery includes business-web evidence, structured Person extraction, decision-maker authority ranking, current-role reconciliation, personhood-quality guards, domain-integrity checks, offer-fit routing, provenance-aware decision-maker-bound contact evidence, hard-bounded batch site review, separate review-ready/outreach-ready contact gates, recent exact public-record/press-release contact provenance, and governed candidate review. The first real outreach-ready buyer has now progressed through production intent creation and human approval; no send has occurred yet.
- Buyer-discovery website evidence now shares the first-party rule with Lead Scoring/Search Fabric: directory/social platform URLs contribute no website score, cannot seed generated work-email patterns, and are never probed as company sites. Accepted `identity_or_direct` acquisition evidence can provide a provenance-preserving first-party website fallback without mutating the canonical prospect row, and canonical first-party evidence wins when present. Public decision-maker evidence is separately fail-closed: official-site role evidence may stand alone, otherwise two independent business-correlated sources must agree on the same person/authority; this never creates contact/outreach authority by itself. An OBSERVE-only buyer-readiness dossier now combines company, decision-maker/contact and existing commercial-activation gates into ordered blockers. All Star Roofing currently reaches corroborated Terry Paris/Owner but remains blocked on a verified person-bound contact, then buyer-record creation. ✅ local/tested
- Governed Resend outbound with approval, idempotency, opt-out and postal-footer compliance. Canonical DB layer + fail-closed Resend provider adapter + dedicated sender transport are live/tested. Outbound Governor policy engine now automates evidence/compliance decisions across OBSERVE, ASSIST and explicitly enabled GUARDED_EXECUTE modes while preserving role-separated approval/send boundaries.
- Reply/provider lifecycle capture. Signed-webhook normalization + per-intent reply alias + exact-sender binding + deterministic reply classification + provider delivery/bounce/complaint/open/click capture are local/tested. Three forward-only DB hardening migrations, reply-ingest credentials, service routing and live webhook enablement remain the final activation work.
- New Supabase-backed AI Closer; legacy SQLite closer execution is retired from active flow. Canonical case/recommendation/human-advance state machine + separated observer/planner/approver runtime identities + OBSERVE-only closer worker are local/tested; canonical migration/credential/service activation remains gated.
- Commercial proposal states without fabricated prices or fake settlement.
- Buyer activation only after verified commercial evidence.
- USDT/BSC payment request + independent on-chain verification.
- First genuine paid buyer recorded as actual revenue in Supabase.

Phase 3F deliverables:
- Append-only delivery outcome, conversion and buyer-satisfaction evidence. ✅ local/tested
- Evidence-derived actual revenue, cost and gross profit from verified BSC direct payment or released escrow only. ✅ local/tested
- Exact approved USD price ↔ USDT settlement invariant; overpayment is not silently counted as revenue. ✅ local/tested
- Canonical feedback projection + Python adapter for Omega/revenue intelligence and Astra priorities. ✅ local/tested
- Hard commercial figures scorecard: actual revenue/cost/gross profit/margin, conversion, buyer satisfaction and buyer/niche profitability via a dedicated read-only role. ✅ local/tested
- OBSERVE-first bounded revenue-recognition worker + systemd timer. ✅ local/tested
- Canonical Lead Intelligence convergence: both lead intake compatibility URLs now feed canonical prospects; evidence-preserving read projection over prospects → acquisition provenance → identity → Intelligence Fabric → qualification is local/tested with a dedicated SELECT-only role. ✅ local/tested
- Read-only canonical-vs-legacy parity engine/CLI is local/tested; it uses only the dedicated Lead Intelligence DSN plus SQLite mode=ro, reports ambiguity/mismatches without reconciling or mutating data. ✅ local/tested
- Lead Intelligence SELECT-only reader role migration is applied in canonical Supabase; runtime credential activation remains gated. Production inspection found 29,807 prospects, 12,184 active identity links, 1,177 qualifications, 466 prospects with both identity + qualification, and only 1 acquisition-ledger row; legacy SQLite crm_leads/lane_leads are empty.
- Intelligence Materializer planner + dedicated append-only writer contract are local/tested: observed prospect facts plus evidence-aware v2 qualification scores (legacy v1 compatibility only), deterministic evidence hashes, v2 confidence sourced from persisted evidence_confidence, unknown dimensions preserved, INSERT-only facts/scores, and no unrelated commercial authority. ✅ local/tested
- Intelligence Materializer schema/role migrations are active in canonical Supabase. One explicitly approved All Star Roofing proof materialized four canonical prospect facts plus one v2 qualification score; runtime credential activation and any bulk historical materialization remain gated. ✅ bounded production proof
- Lead Scoring v2 evidence-aware qualification is local/tested: missing evidence remains unknown instead of zero, directory/social profile URLs cannot count as first-party website evidence, quality and evidence confidence are separated, and low-confidence records become insufficient_evidence. Corrected read-only production inspection shows all 466 identity+qualification prospects still require first-party enrichment: all 466 populated website fields are directory/platform URLs, 164 have phone evidence, none has a first-party website candidate, and the maximum currently observable completeness is 30. ✅ local/tested
- Lead Scoring v2 schema is active in canonical Supabase. One explicitly approved bounded All Star Roofing v2 qualification now coexists with its unchanged v1 row. Buyer allocation now prefers v2 with v1 fallback, independently enforces the v2 evidence-confidence floor, and requires active canonical identity/entity agreement before allocation planning; allocation execution and bulk v2 writes remain gated. ✅ local/tested consumer cutover
- Evidence Enrichment Planner is local/tested: converts v2 confidence gaps into bounded first-party evidence targets, counts only scorer-consumed fields, treats projections as upper bounds, and never performs network work or mutation. ✅ local/tested
- Bounded real-web enrichment execution remains separate from planning; evidence must pass canonical acquisition/Search Fabric discovery + identity guard + site-probe checks before v2 can count it.
- Evidence-backed singleton identity planning is local/tested and fail-closed; it does not relax the bulk duplicate resolver. All Star Roofing (Austin) satisfied accepted direct acquisition provenance + exact phone/name + verified first-party domain corroboration, reached quality 86.3 with decision confidence 0.55, and was explicitly approved for one bounded production entity/link + v2 qualification + Intelligence Fabric projection. Outreach remains production-gated. ✅ bounded production proof
- Supabase production security audit found materially over-broad client grants on legacy/internal public-schema tables. First bounded lockdown slice for b2b_leads, empire_revenue_ledger and legacy crypto_payment_requests is local/tested. A second internal operational/control-plane slice covering agent telemetry/config/task, watcher/healer, pipeline-run and business-action tables is also local/tested. Both revoke anon/authenticated access, enable RLS, preserve service_role/admin access and preserve rows. Production application remains gated.
- Remaining production gates: Intelligence Materializer runtime credential activation and bulk materialization, bulk v2 qualification, security-lockdown migrations, buyer-allocation execution, outbound contact, commercial terms and payment execution.

### Empire Coder — Developer Intelligence Layer (HIGH PRIORITY PARALLEL FOUNDATION)
Empire Coder is the governed internal engineering system for building, debugging, testing, improving and maintaining EmpireOS itself.

Foundation status — local/tested, production activation gated:
- OBSERVE-first capability profile and protected-path/secret-file enforcement.
- Targeted repository intelligence with Blueprint-aware context windows.
- Durable task/plan/checkpoint/proposal state plus versioned compact recovery context for long-running engineering jobs.
- Mandatory best-of-N rule: at least two model candidates -> comparative critique -> synthesized final; first output is never actionable.
- The same best-of-N rule governs proposed next commands before command-policy evaluation.
- Knowledge Garden with canonical precedence, ACTIVE/REVIEW/QUARANTINED states, duplicate/stale guidance detection and active-only default retrieval; Blueprint v6 is the highest roadmap/status authority when canonical sources disagree.
- Provider-agnostic model router with local Ollama support.
- Local qwen3-coder:30b installed and benchmarked on the EmpireOS host; Ollama chat requests explicitly disable model-native thinking because Empire Coder already enforces two-candidate + critique + synthesis reasoning and CPU latency is the bottleneck.
- Read-before-write patching, atomic writes and rollback checkpoints.
- Python AST-aware symbol patching plus dependency/reverse-dependency and impacted-test selection.
- Best-of-N structured patch proposals with strict JSON schema, live-file validation and mandatory revalidation immediately before local application.
- Task-scoped knowledge promotion for REVIEW sources only, with explicit approval, reason, content-hash pinning and automatic invalidation after source changes; QUARANTINED sources remain non-promotable.
- Restricted subprocess runner with filtered environment, timeouts and secret-output scrubbing.
- Specialist Architect/Backend/Frontend/QA/Security/Reviewer role definitions with writer/verifier separation.
- Role-aware model routing now separates `planner`, `writer`, and `verifier`: qwen3-coder:30b is the capability-3 writer + hard-plan fallback; optional qwen2.5-coder:14b is auto-detected as capability-2 planner-only when installed; advisory verification must use a distinct configured provider/model or remain explicitly unavailable. ✅ local/tested routing
- Independent verifier with security, diff and test checks.
- Controlled self-build scope that cannot silently widen authority.
- Staged canonical coder_* Supabase schema with a dedicated least-privilege engineering-state role.
- Localhost-only Ollama systemd packaging is installed and enabled for reboot persistence on the EmpireOS host; an already-healthy pre-existing Ollama process remains undisturbed until reboot.
- Disabled-by-default, internal-token-gated `/v1/coder/*` API for task state and proposal-job queueing only; no remote execution/patch/deploy endpoint.
- Resumable local job queue with stale-job recovery and proposal-only PLAN / NEXT_COMMAND worker.
- Coder worker service/timer is installed and enabled; the timer runs one proposal-only worker pass per minute with localhost-only network access and a 30-minute bounded oneshot start timeout for CPU-local 30B jobs. First live PLAN proof completed with two independent candidates, comparative critique, refined persisted proposal, and zero patch execution. ✅ live governed proof

Candidate engineering changes stop at human approval. Commit/push/merge/deploy, production DB changes, service control, outbound, payment/funds and production credentials remain gated.

### Phase 4 — Astra Operating Layer ← CURRENT
Astra becomes the top coordinator for business priorities, agent routing, bottleneck detection, expected-value decisions, resource allocation, cost control and approval policies. Premium AI is used only when expected value justifies the cost.

Phase 4 observer/calibration implementation status — ✅ local/tested, production activation gated:
1. Astra Observer DB Role ✅ — restricted read-only `empire_astra_observer`; dedicated login remains passwordless/unprovisioned.
2. Astra Role Transport ✅ — locked RPC transport permits only `get_commercial_outcome_feedback(integer)` for the observer role.
3. Outcome Calibration Engine ✅ — real Phase 3F conversion/revenue/cost/gross-profit/satisfaction/repeat-purchase calibration with explicit readiness thresholds.
4. Astra Observer Worker ✅ — bounded feedback read, OBSERVE-only runtime, atomic local snapshot, no fabricated operational counts.
5. Astra Decision Integration ✅ — verified negative-margin outcomes can elevate a review recommendation without changing prices, budgets, model weights or commercial state.
6. Astra Operating Board V1 ✅ — deterministic ranked executive work queue across observed workstreams, preserving approval boundaries and intelligence routing while `decide()` remains backward-compatible through the board's primary item. OBSERVE-only; no execution authority.
7. Phase 4 Test Suite ✅ — Python, isolated PostgreSQL role/permission, fail-closed CLI and systemd verification are green.
8. Runtime Packaging ✅ staged — env template plus `empire-astra-observer.service` / timer exist but are not installed or enabled.
9. Documentation ✅ — `docs/PHASE4_ASTRA_OBSERVER.md`.
10. Activation Readiness Gate ✅ local/tested — preview-only readiness distinguishes OBSERVE deployment prerequisites from consequential-authority prerequisites; the latter cannot pass until the genuine first-revenue loop is verified.

Phase 4 authority remains OBSERVE. The canonical Supabase migration, observer credential provisioning and service activation remain production gates. A genuine buyer → verified payment → outcome → feedback loop is still required before Astra receives consequential commercial authority, but it no longer blocks Phase 4 engineering.

### Phase 5 — Organic Growth Engine
SEO, AEO, GEO, keyword intelligence, topic clusters, programmatic pages, AI Cards, citation/mention monitoring, authority/backlink graph, competitor citation gaps, public publishing, first-party tracking and content→revenue attribution.

#### Empire Search Intelligence Engine — PARALLEL FOUNDATION
The proprietary Search Intelligence foundation is being built early in parallel with Phase 3F/4 because it is safe, reversible growth infrastructure and increases product value without bypassing revenue or autonomy gates.

Foundation scope:
- canonical Search Page + Search Opportunity models;
- deterministic opportunity scoring with unknown external metrics left null;
- mandatory Content Quality Firewall;
- metadata, JSON-LD, canonical and indexability recommendations;
- explicit auditable indexation lifecycle;
- OBSERVE-only SearchCommander;
- read-only/recommendation FastAPI surface under `/v1/search/*`, now with a stable `search-v1` repository contract/envelope and fail-closed default when no canonical repository is configured;
- forward-only canonical Supabase schema with tenant/site isolation and search→commercial attribution links; staged least-privilege `empire_search_reader` role + transaction-read-only PostgreSQL repository are local/tested, with RLS tenant scope enforced by `app.tenant_key` and no production credential/application yet;
- Search Console adapter contract + credential/status gate is local/tested and disabled by default; it exposes no credential contents and cannot fetch observations until a real adapter and credential activation are separately approved. Search Fabric-backed SERP snapshots are local/tested as evidence-only adapters: observed ranking positions/provenance are preserved, missing positions are never invented, and failed retrieval remains explicitly unavailable. Evidence-backed competitor gap analysis is also local/tested and derives only observed coverage/presence/gap/best-position/domain signals; broader market metrics stay unknown unless real evidence exists;
- programmatic SEO prohibited from auto-publishing or auto-indexing;
- legacy AEO direct-publish code is compatibility-only and will be governed behind the new layer rather than expanded.

Search Fabric remains the retrieval/discovery substrate. Search Intelligence is the quality, governance, AEO/GEO, opportunity and commercial-attribution layer above it.

Search Command Centre foundation ✅ local/tested: `apps/search-command-centre/` is a Next.js 16 + TypeScript + Tailwind server-rendered dashboard for Organic Revenue, opportunities, page intelligence, alerts and Search Console readiness. A `/technical` drill-down now covers repository-backed indexation, content-decay and cannibalisation evidence. It consumes governed `search-v1` APIs via a server-only API binding, renders gated/unknown states instead of fabricated zeros, and is not the source of truth.
AEO/GEO/citation evidence slice ✅ local/tested: staged tenant-scoped `seo_ai_visibility_observations`, read-only repository/API access and evidence-only preview analysis record observed cited URLs/positions/provenance. No observation means visibility is unavailable rather than zero; no publishing, provider mutation or synthetic AI-visibility score exists.
Authority/backlink graph slice ✅ local/tested: staged tenant-scoped `seo_backlink_observations`, read-only repository/API access and evidence-only graph analysis expose observed links, referring domains, rel state and provenance. Missing observations remain unavailable and no synthetic authority score or link-building execution exists.
Competitor citation-gap slice ✅ local/tested: observed AI-citation evidence now distinguishes competitor-cited/Empire-absent gaps from Empire-present results and no-evidence unknowns. No inferred mentions, synthetic visibility score or execution authority is introduced.

Production database migration, Search Console credentials, sitemap/index submission, content publishing, redirects and robots/canonical mutation remain explicitly gated.

### Phase 6 — A2A Commerce Network

Second slice ✅ local/tested: signed-claim freshness, one-time nonce replay protection and persisted identity provenance are staged behind dedicated roles; no execution/payment/allocation authority is enabled.
A2A Agent Card/protocol, authenticated agent discovery, agent buyers/suppliers, AI-to-AI quoting, negotiation and tasks, commercial gates, marketplace and revenue attribution. Public discovery stays low-risk; activation/payment/allocation remain governed.

Foundation slice ✅ local/tested: `/a2a/v1/discovery` now publishes machine-readable separation between public read-only capabilities and future authenticated commercial capabilities. Quote/negotiation/task capabilities are discovery-only with authentication + human approval required; execution, payment and allocation remain unexposed.

Second slice ✅ local/tested: authenticated agent identity now supports a non-executing `commerce.intent` scope in addition to discovery. A staged append-only `a2a_commercial_intents` contract + dedicated NOLOGIN RPC role records quote/negotiation/task requests as `pending_approval`; the fail-closed `/v1/a2a-commerce/intents` API remains unbound by default. No approval, execution, payment or allocation RPC exists in this slice.

Third slice ✅ local/tested: deterministic A2A negotiation transition previews now enforce human approval and terminal-state rules. `approved_for_manual_execution` never grants payment, allocation or task-execution authority; all negotiation lifecycle outputs remain OBSERVE-only.

Fourth slice ✅ local/tested: evidence-only manual-handoff review now requires an approved-for-manual-execution negotiation plus signed-agent identity provenance, negotiation evidence, explicit human-approval evidence, counterparty acknowledgement and a manual-handoff reference. Passing the review only makes the packet ready for operator review; payment, allocation, task execution and autonomous handoff remain hard-disabled.

Fifth slice ✅ local/tested: manual-handoff readiness now validates chronology and freshness across negotiation, human approval, counterparty acknowledgement and operator-handoff evidence. Missing, stale, future-dated or out-of-order evidence blocks readiness; payment, allocation, task execution and autonomous handoff remain hard-disabled.

### Phase 7 — Conversation OS

Second slice ✅ local/tested: provider ingestion now records deterministic payload hashes, requires timezone-aware event timestamps and treats exact replay as idempotent while rejecting altered payloads under the same provider-event ID. Persistence remains append-only and provider sends/calls/bookings stay disabled.

Vonage, ElevenLabs, streaming voice, barge-in, tone mirroring, summaries/transcripts, AI qualification/closing, human escalation, booking, objections, DISC/coaching, dynamic offers and unified conversation history across email/voice/A2A/CRM.

Foundation slice ✅ local/tested: canonical `empire_conversations` + append-only `empire_conversation_events` are staged as the shared channel-neutral history layer across email/SMS/voice/A2A, linked to existing prospects, entities, buyers, opportunities and closer cases. No provider ingestion writer, Vonage call, ElevenLabs streaming, outbound, booking or production migration is activated.

Second slice ✅ local/tested: provider-event ingestion now has a dedicated append-only NOLOGIN RPC role and fail-closed `/v1/conversations/events/ingest` boundary. Existing canonical conversation IDs are required; provider/external IDs are consistency-checked and provider event IDs are idempotent. The default hub binding remains unconfigured, and no provider activation, send, call, voice streaming or booking authority is introduced.

Third slice ✅ local/tested: dedicated SELECT-only Conversation reader plus `/timeline` and deterministic `/summary` surfaces now expose unified observed history. Missing events remain unknown, outbound-only history is explicitly unanswered, and no sentiment/qualification fact is invented; provider sends, calls, streaming and booking remain disabled.

Fourth slice ✅ local/tested: evidence-only qualification review now accepts qualification signals only when they are explicitly attached to an inbound canonical event with transcript and evidence references. Plain transcript text is never interpreted into interest, need, authority, timing, budget or sentiment; missing transcript/signal evidence remains explicit. Send, call, voice-streaming and booking authority stay disabled.

Fifth slice ✅ local/tested: qualification freshness review now checks every explicit inbound qualification signal timestamp against a bounded freshness window. Stale, future-dated or missing explicit qualification evidence blocks operator review, while plain transcript text still cannot create inferred qualification. Send, call, voice-streaming and booking authority stay disabled.

### Phase 8 — Revenue CRM

Second slice ✅ local/tested: next-action recommendations now require canonical conversation/closer/fulfilment/buyer evidence refs, preserve unknown capacity as unknown, and can cite verified buyer capacity without mutating CRM state or sending follow-up.

Prospect/buyer graph, conversations, pipeline, deal probability, next action, follow-ups, preferences, territory/capacity, offers/contracts/payments, retention, expansion and customer success.

Foundation slice ✅ local/tested: staged read-only `revenue_crm_prospects` and `revenue_crm_buyers` projections compose canonical prospects, Conversation OS, closer state, fulfilment state and buyer activation/capacity. `deal_probability` remains NULL until a calibrated evidence-backed model exists; no follow-up automation, payment action, CRM mutation or production migration is activated.

Second slice ✅ local/tested: Revenue CRM now exposes an evidence-backed `next-action` recommendation surface using only observed closer, conversation and fulfilment state. Unknown evidence yields no action; every recommendation is approval-required with `execution_authority=none` and cannot send follow-up or mutate CRM state.

Third slice ✅ local/tested: prospect close-readiness now requires an engaged canonical conversation, commercially-ready closer case, verified price, activated buyer with verified positive capacity, and fulfilment readiness. Missing evidence remains an explicit blocker; follow-up, payment and CRM mutation remain disabled.

Fourth slice ✅ local/tested: retention/expansion readiness now requires activated-buyer, verified-payment, delivered-fulfilment and observed-outcome evidence. Expansion additionally requires an explicitly verified successful outcome plus verified positive buyer capacity; unknown outcome success remains unknown. No follow-up, payment, CRM or offer mutation is introduced.

Fifth slice ✅ local/tested: retention/expansion freshness review now validates chronology across buyer activation, verified payment, fulfilment and observed outcome, and independently checks capacity freshness for expansion. Stale, future-dated, missing or out-of-order evidence blocks the relevant review while retention remains separable from expansion-only blockers. No follow-up, payment, CRM or offer mutation is introduced.

### Phase 9 — Advertising Brain

Second slice ✅ local/tested: canonical ad observations now carry deterministic payload provenance, timezone-aware observation timestamps, optional explicit canonical creative identity, and tamper-aware idempotency. Exact provider replays stay idempotent; changed metrics or creative identity under the same observation ID conflict. Campaign/budget/pause/retarget authority remains disabled.

Google/Meta integrations, video/ad factory, UGC/avatar creative, A/B testing, media buying, ROAS/profit optimisation, budget allocation, retargeting and landing-page feedback loops.

Foundation slice ✅ local/tested: staged canonical `ad_accounts`, `ad_campaigns`, `ad_creatives` and append-only `ad_performance_observations` provide a measurement spine for spend, attributed revenue, attributed gross profit, clicks, impressions and conversions. ROAS/profit-ROAS stay unknown when attribution is missing; no campaign launch, budget mutation, pause, retargeting or production migration is activated.

Second slice ✅ local/tested: provider observations can now be normalized into an existing canonical campaign through a dedicated append-only NOLOGIN RPC role. Provider observation IDs are idempotent, attribution nulls remain null, and the fail-closed ingest API has no campaign creation, budget, pause or retarget authority.

Third slice ✅ local/tested: campaign economics review now aggregates observed spend/conversions and exposes ROAS/profit-ROAS only when attribution evidence is complete. Partial attribution remains unknown rather than zero; budget, pause and retarget execution stay disabled.

Fourth slice ✅ local/tested: advertising evidence review now checks observation freshness and produces creative-level economics only from explicitly identified creatives. Creative comparison is available only when at least two creatives have complete revenue/profit attribution; stale/future observations, missing creative identity and incomplete attribution remain explicit blockers. No campaign creation, budget, pause or retarget mutation is introduced.

Fifth slice ✅ local/tested: creative economics drift review compares fresh baseline and current observation windows for the same canonical creative identities, deriving observed ROAS/profit-ROAS deltas only when attribution is complete. Missing creative matches, stale evidence or incomplete attribution blocks comparison; no campaign creation, budget, pause or retarget mutation is introduced.

### Phase 10 — Predictive Cloud V3
Trend Radar, market/demand/business/buyer/revenue/profit forecasts, churn, LTV, capacity, conversion, Horizon forecasts, Revenue GPS and connected Business/Buyer/Signal/Revenue graphs.

Foundation slice ✅ local/tested: `predictive_cloud_v3` now supports bounded explainable directional forecasts from canonical observed time series only, with a seven-observation minimum gate, explicit trend slope/R²/evidence confidence, and `insufficient_history` instead of guessed direction. Staged forecast/signal tables are read-only to the current service role; no autonomous commercial execution or production migration is activated.

Second slice ✅ local/tested: an idempotent forecast registry now records only available forecasts that satisfy the seven-observation evidence gate, with model name/version, forecast key and provenance. Insufficient-history previews cannot be registered. The fail-closed registry/read API remains OBSERVE-only with no commercial execution authority.

### Phase 11 — Experiment + Causal Engine
Controlled experiments, counterfactuals, holdouts, creative/offer/pricing/page tests, incrementality and causal attribution.

Foundation slice ✅ local/tested: deterministic holdout/treatment assignment planning and append-only experiment outcome observations are staged around the existing `gtm_experiments` model. Incrementality is computed only when each arm has sufficient observed samples; no live traffic mutation, automatic rollout, pricing change or production migration is activated.

Second slice ✅ local/tested: observed experiment analysis now gates causal-review eligibility on sample sufficiency plus verified assignment integrity, exposure integrity and a closed outcome window. Failed integrity remains observed lift only; no rollout, traffic or pricing mutation is exposed.

Third slice ✅ local/tested: append-only experiment registry records evidence-backed hypothesis/metric/variant definitions plus assignment/exposure integrity and outcome-window state. Registry writes are idempotent and OBSERVE-only; live traffic, rollout and pricing mutation remain unavailable.

Fourth slice ✅ local/tested: causal-review conclusion packets/history now require sufficient observed arm samples, verified assignment integrity, verified exposure integrity and a closed outcome window. The conclusion records observed lift direction/size while explicitly marking statistical significance unavailable; the staged append-only registry recomputes lift from observed means and cannot enable traffic, rollout or pricing mutation.

Fifth slice ✅ local/tested: causal-conclusion freshness review now requires the closed outcome window to occur after the experiment observation and remain within a bounded freshness window. Stale, future-dated or chronologically invalid conclusion evidence blocks current operator review without invalidating the historical observed lift packet; traffic, rollout and pricing mutation remain disabled.

### Phase 12 — Demand Genesis
Create demand through content, ads, offers, voice, AEO/GEO, communities, partnerships and agent distribution rather than only harvesting existing demand.

Foundation slice ✅ local/tested: governed demand-plan and evidence records are staged across content/AEO/GEO/community/partnership/agent-distribution/ads/voice channels. Plans require evidence, explicit success metrics and approval, while execution authority is hard-locked to `none`; no publishing, outbound, ad spend, provider activation or production migration is enabled.

Second slice ✅ local/tested: demand readiness analysis now requires observed demand signals, audience, conversion and cost evidence before a plan can be operator-review ready. Missing evidence remains explicit and publishing, outbound, ad-spend and provider activation stay disabled.

Third slice ✅ local/tested: governed demand-plan registry persists only review-ready evidence-backed plans with idempotent read-only history. Publishing, outbound, ad-spend and provider activation remain hard-disabled.

Fourth slice ✅ local/tested: observed demand outcome feedback now compares the plan success metric against later evidence-backed outcomes and preserves missing outcome evidence as unknown. Feedback never enables publishing, outbound, ad spend or provider activation.

Fifth slice ✅ local/tested: demand outcome evidence review now checks outcome freshness and plan→outcome chronology before exposing observed cost per positive incremental success-metric unit. Missing cost, stale/future outcomes, outcome-before-plan evidence and flat/negative incremental outcomes remain explicit/unknown rather than receiving synthetic efficiency. Publishing, outbound, ad spend and provider activation remain disabled.

### Phase 13 — Revenue Exchange
Inventory marketplace, real-time pricing, exclusives, territories, human/agent buyers, supply-demand pricing, capacity-aware allocation and Revenue Lanes.

Foundation slice ✅ local/tested: staged `revenue_exchange_observations` and a typed exchange snapshot separate inventory/capacity/verified-price intelligence from execution. Supply-demand ratio and observed price ranges are derived only from canonical evidence; allocation, exclusivity enforcement, settlement and production migration remain governed and unexposed.

Second slice ✅ local/tested: Revenue Exchange market assessment now classifies observed inventory-vs-capacity balance and verified price ranges for review only. Allocation, pricing and settlement authority remain `none`.

Third slice ✅ local/tested: Revenue Exchange observations now support idempotent append-only ingestion through a dedicated NOLOGIN RPC role and fail-closed API. Observation keys, source provenance and evidence are preserved; allocation, pricing, exclusivity and settlement remain unexposed.

Fourth slice ✅ local/tested: exact source reconciliation now compares observed inventory, buyer capacity and verified-price sets against independent canonical evidence. Missing/mismatched evidence produces explicit blockers; allocation, pricing and settlement authority remain `none`.

Fifth slice ✅ local/tested: reconciled market-drift review now checks current/baseline evidence freshness and chronology before comparing inventory, buyer capacity, supply-demand ratio and observed verified-price ranges. Drift is unavailable when the current snapshot is stale/future, the baseline is invalid/stale, or canonical reconciliation fails; unsupported ratio/price deltas remain unknown. Allocation, pricing and settlement authority stay `none`.

Sixth slice ✅ local/tested: allocation-readiness review now requires a fresh current snapshot, exact canonical reconciliation, positive qualified inventory, positive verified buyer capacity and at least one verified price before an operator allocation review is considered ready. Allocation, pricing, exclusivity and settlement authority remain `none`; no matching or funds movement is introduced.

### Phase 14 — Digital Twin
Simulate markets, campaigns, pricing, buyers, inventory, sales capacity, ad spend and offers before deploying real capital.

Foundation slice ✅ local/tested: deterministic market scenarios now require an observed baseline with provenance plus explicit demand/capacity/price assumptions. Results are permanently labeled `simulation_only=true` and `actual_revenue=false`; no real spend, campaign/pricing mutation or production execution is enabled.

Second slice ✅ local/tested: Digital Twin scenario comparison now quantifies simulated revenue delta versus the observed baseline while preserving `simulation_only=true`, `actual_revenue=false` and zero execution authority.

Third slice ✅ local/tested: append-only scenario/result registry persists immutable observed-baseline provenance plus simulated results with idempotent history. Capital, campaign and pricing execution remain hard-disabled.

Fourth slice ✅ local/tested: realization review compares simulated served units and projected revenue with later observed outcomes. Revenue error is calculated only when recognized-revenue evidence is explicit; missing recognition stays unknown, and the review itself never creates actual revenue or execution authority.

Fifth slice ✅ local/tested: append-only realization registry/history persists observed-vs-simulated review evidence behind dedicated NOLOGIN writer/reader roles. The database recomputes served-unit/revenue error from the registered scenario result, stores unrecognized revenue as NULL, and hard-locks actual-revenue creation plus capital/campaign/pricing execution to false. The migration is staged only and is not applied to production.

Sixth slice ✅ local/tested: Digital Twin calibration readiness now requires a realized outcome to occur after the observed baseline, remain within a bounded freshness window and expose recognized-revenue comparison before simulation error can be used for model-review feedback. Stale/future/pre-baseline outcomes or missing recognized revenue block calibration readiness; simulation cannot mutate model weights or execute capital, campaign or pricing actions.

### Phase 15 — Capital Allocator
Astra evaluates expected return, risk, cost, cash, confidence and time-to-revenue to decide where the next unit of capital should go.

Foundation slice ✅ local/tested: recommendation-only capital assessments now derive expected-return multiple, downside ratio, time factor and risk-adjusted score from explicit evidence-backed inputs. Recommendation records are hard-locked to `execution_authority=none`; no funds movement, budget mutation or production apply is enabled.

Second slice ✅ local/tested: operator capital-review policy now blocks recommendations below confidence/risk-adjusted thresholds or above downside limits. Review eligibility never moves funds or mutates budgets.

Third slice ✅ local/tested: append-only capital review registry records candidate economics, policy thresholds, blockers and evidence for operator review. Funds movement and budget mutation remain impossible from this surface.

Fourth slice ✅ local/tested: realized-return feedback now compares expected return against independently observed recognized revenue and observed cost. Missing revenue/cost evidence remains unknown; feedback cannot move funds or mutate budgets.

Fifth slice ✅ local/tested: capital outcome calibration now checks freshness and recommendation→outcome chronology before comparing the recorded expected-return multiple with later realized-return multiple. Missing recognized revenue/cost, stale/future outcomes and pre-recommendation outcomes keep calibration unavailable; no recommendation mutation, funds movement or budget mutation is introduced.

### Phase 16 — SaaS / Network Scale
Canonical multi-tenant teams, RBAC, usage metering, subscriptions and network-scale tenancy controls.

Foundation slice ✅ local/tested: staged `saas_tenants`, `saas_memberships`, `saas_usage_observations` and subscription-state reads establish canonical tenant identity, RBAC and usage evidence. Existing billing/subscription mutation paths are not expanded; no billing execution, tenant migration or production credential change is activated.

Second slice ✅ local/tested: SaaS/network-scale readiness now reviews observed utilization, active subscription state, tenant-isolation evidence and optional white-label readiness. Output is approval-only with provisioning and billing execution hard-false.

Third slice ✅ local/tested: tenant-scoped readiness registry persists only review-ready scale evidence with idempotent history. Tenant provisioning, API-key issuance, billing and subscription mutation remain disabled.

Fourth slice ✅ local/tested: developer/API-access readiness now requires active membership, owner/admin role, active subscription, verified tenant isolation and allowlisted read scopes. Mutating scopes are rejected; no API-key secret material is generated and issuance/revocation stay disabled.

Fifth slice ✅ local/tested: SaaS quota readiness now checks freshness independently for observed usage, subscription state and tenant-isolation evidence before exposing utilization/headroom. Missing or zero limits, over-limit usage, inactive subscriptions, unverified isolation and stale/future evidence remain explicit blockers; no provisioning, billing, subscription mutation or API-key issuance is introduced.

Sixth slice ✅ local/tested: API-access freshness review now requires membership, subscription and tenant-isolation evidence to remain within a bounded freshness window in addition to the existing admin-role, active-subscription and read-scope gates. Stale or future-dated evidence blocks issuance review; API-key issuance/revocation, secret generation and subscription mutation remain disabled.

Multi-tenant architecture, teams/RBAC, usage billing, USDT subscriptions, white label, custom domains, affiliate/agency/client dashboards, API keys, developer platform and marketplace/partner network.

### Phase 17 — Enterprise
Auditability, permissions/data isolation, SLA/compliance/security monitoring, backup/DR, multi-region, Kubernetes, Kafka, ClickHouse/Grafana, queues, model registry and retraining when justified by real load.

Foundation slice ✅ local/tested: tenant-scoped enterprise control evidence and SLO observations are staged for access control, data isolation, auditability, security monitoring, backup/DR, reliability and compliance. Missing telemetry remains `unknown`; no Kubernetes/Kafka/multi-region/infrastructure migration or production deployment is activated.

Second slice ✅ local/tested: Enterprise readiness aggregation now blocks review on any control/SLO failure or unknown and requires both control evidence and SLO observations. Execution authority remains `none`.

Third slice ✅ local/tested: append-only enterprise readiness registry stores observed control/SLO evidence snapshots and derived blockers without any infrastructure, identity, backup, SLO-target or compliance mutation authority.

Fourth slice ✅ local/tested: preview-only enterprise evidence review now checks control/SLO observation freshness and derives SLO margin trends only from comparable observed values. Stale/future evidence is explicit, insufficient or unknown SLO values preserve `unknown` trend state, and no infrastructure, identity, backup, SLO-target or compliance mutation authority is introduced.

Fifth slice ✅ local/tested: Enterprise drift review compares prior and current control/SLO evidence only when both snapshots are fresh, chronologically valid and structurally comparable. Control state direction and SLO margin trend are derived from observed evidence; missing matches, unknown SLO values and stale/future evidence remain explicit blockers. No infrastructure, identity, backup, SLO-target, compliance or control mutation authority is introduced.

### Phase 18 — Full Autonomous Revenue OS
Astra detects → predicts economics → selects market → creates acquisition/content/ads → finds buyers → runs conversations → closes → verifies payment → delivers → measures actual profit → learns → reallocates.

Foundation slice ✅ local/tested: OBSERVE-only `RevenueDecisionPacket` integration composes Astra workstream recommendations, Predictive Cloud direction, capital recommendation references, demand-plan references, enterprise blockers and explicit evidence refs. Missing signals remain unknown; packets are hard-locked to `side_effects=none` and `execution_authority=none`, so no autonomous spend, outreach, payment, allocation or deployment is enabled.

Second slice ✅ local/tested: Revenue OS readiness now gates operator review on complete Astra workstream/job, forecast direction, capital candidate, demand plan and zero enterprise blockers. Packets remain OBSERVE-only with no side effects.

Third slice ✅ local/tested: governed Revenue OS packet registry now persists composed packets together with readiness state and evidence while hard-locking spend, outreach, payment, allocation and deployment execution to false.

Fourth slice ✅ local/tested: component-level freshness review now gates Astra, Predictive, Capital, Demand and Enterprise evidence by explicit observed timestamps. Missing, stale or future-dated evidence blocks operator review; no execution path is introduced.

Fifth slice ✅ local/tested: OBSERVE-only Revenue OS learning feedback links a decision packet to later commercial outcome, recognized-revenue and observed-cost evidence. Gross profit is derived only when recognized revenue and cost are both present; missing evidence remains explicit and no model-weight mutation, capital reallocation, spend, outreach, payment, allocation or deployment authority is introduced.

Sixth slice ✅ local/tested: Revenue OS learning-readiness now requires outcome evidence to occur after the decision packet and remain within an explicit freshness window. Pre-decision, stale or future-dated outcomes block learning readiness even when revenue/cost evidence is otherwise complete; no model-weight mutation, capital reallocation, spend, outreach, payment, allocation or deployment authority is introduced.

### Governed Control-Plane API Layer — Phases 4–18
Second-pass API layer ✅ local/tested and mounted in the hub. Health/read/preview surfaces now exist for Astra, A2A identity, Conversation OS, Revenue CRM, Advertising Brain, Predictive Cloud, Experiment/Causal analysis, Demand Genesis, Revenue Exchange, Digital Twin, Capital Review, SaaS tenancy, Enterprise readiness and Revenue OS. Repository/provider-backed surfaces mount unbound and fail closed until their canonical reader or verifier is explicitly activated; pure analysis/simulation previews remain non-mutating. All routes expose OBSERVE/SIMULATION status and explicit zero execution authority.

Current route families: `/v1/astra/*`, `/v1/a2a-identity/*`, `/v1/conversations/*`, `/v1/revenue-crm/*`, `/v1/advertising/*`, `/v1/predictive/*`, `/v1/experiments/*`, `/v1/demand/*`, `/v1/revenue-exchange/*`, `/v1/digital-twin/*`, `/v1/capital/*`, `/v1/saas/*`, `/v1/enterprise/*`, `/v1/revenue-os/*`.

Production repositories, provider credentials, trusted keys, migrations and consequential execution remain separate approval gates.

## Retain and Upgrade
- Cinematic Landing, Truth Portal, Ghost Ledger privacy concepts, Hall of Fame, Sniper Leaderboard, Live Strike Zone and Partner Network.
- Self-improving landing pages, Whale Hunter, Storm Chaser, Satellite Scout, high-ticket cinematic demos and pay-per-call.
- Partner/affiliate, done-for-you ads + SEO, agency white-label and private-data/whale-data concepts.
- Treasury/commercial proof, on-chain verification, crypto billing and agent commerce — upgraded onto current USDT/BSC + governed architecture.
- Hermes remains useful as a specialist agent/prompt layer; Astra is the operating coordinator above agents.

## Retire from Active Architecture
- Solana/USDC/Phantom/Anchor/Solana Pay/Helius settlement paths.
- Legacy SQLite as business source of truth.
- Legacy AI closer behaviour that invents settlement amounts or changes funnel states without evidence.
- Simulated/fabricated settlement, fake revenue and placeholder buyer activation.
- Legacy synthetic runtime augmentation, finance replay, autonomous funnel mutation and mock marketplace settlement are retired/fail-closed.
- Direct public access to allocation, activation, settlement, treasury or campaign mutation endpoints.
- Legacy public marketing/AEO publish-delete, AGI marketing publish, Solana/USDC A2A negotiation and SQLite product-registration mutation routes are retired with explicit fail-closed responses.
- Legacy public tenant/billing, Solana payout submit/verify, buyer self-serve signup, lane seat/routing, PPC charge/invoice, SQLite outbox mutation, AGI sales tick and Innovator lane-creation routes are also retired fail-closed; canonical Supabase/BSC/governed replacements remain the only active architecture path.
- `/v1/hub/intake` now converges business leads onto canonical Supabase prospect ingestion with no `lane_leads` fallback; storm alerts no longer create fake CRM prospects, and legacy outreach register/touched SQLite mutations are retired.
- Canonical prospect consent is staged as append-only grant/revoke evidence with a latest-state view and governed `/v1/consent/*` API. The old damage-consent SQLite mutation/read routes are retired, the opt-in landing page now POSTs to canonical consent, and consent recording never implies outbound send authority.
- Public hub hardening milestone: direct SQL mutation calls have been eliminated from `empire_os/hub.py`; remaining legacy carrier roster inspection is read-only and public carrier scrape/batch writers are retired.
- Public execution hardening: direct shell video rendering, public cross-agent dispatch, legacy revenue worker ticks, remote delegated scanning, AGI scout ticks and unauthenticated swarm event-file writes are retired. Cinematic landing generation is now an escaped in-memory preview (`published=false`), and media scheduling is recommendation-only.
- Legacy funnel/traffic mutation, Solana buyer auto-onboarding, public swarm worker-config writes, homeowner job/match/status transitions and carrier-application create/update/autofill routes are retired; canonical acquisition, Revenue CRM, governed matching and partner flows are the active path.
- Direct decision approval/funnel transition, legacy damage/sweep execution, unsigned hub Resend webhook, strike-pack delivery, Telegram sends, direct enrichment and legacy CRM/ICP mutation/import routes are retired; signed webhook, Source Mesh, Evidence Enrichment, Revenue CRM and governed approval/fulfilment flows replace them.
- Canonical read-boundary milestone: legacy Solana/USDC commercial reads, SQLite tenant/lane/PPC/CRM/homeowner/carrier dashboards, payout transaction builders, stale pricing surfaces and legacy outreach/sample reads are retired with explicit canonical replacement pointers. Public hub no longer exposes legacy SQLite commercial truth as an authoritative read model.
- Internal-surface boundary: raw prompt-library bodies, agent topology/process metadata, SOUL files, file-backed swarm/debug histories, legacy Resend/damage/SEO histories and single legacy lead reads are retired. Public GET surfaces no longer expose absolute server paths, private agent IPs, PIDs/restarts or raw internal prompt files.
- Legacy SKU-entitlement delivery is retired across idle-watch, warehouse, lead-engine, Skillspector, OpenCut, templates, Hermes, lead-lane, satellite-wastage and Marketingskills routes. Duplicate FastAPI route registrations were removed and a regression invariant now requires unique method+path registrations.
- Final active hub surface contract: email/copy endpoints are draft-only (`sent=false`, no execution authority) and use the canonical USDT/BSC commercial rail; legacy file-backed SEO audit ingestion is retired; mass-tort direct intake is observation-only (`persisted=false`).

## Infrastructure Gated Until Economically Justified
Docker/Kubernetes, Kafka, Redis/queues, ClickHouse/Grafana, multi-region deployment, heavy model-serving infrastructure and continuous retraining remain later-stage tools. They activate only when measured scale, reliability or revenue requirements justify the complexity.

## Immediate Execution Order
1. Complete canonical Lead Intelligence convergence and security prerequisites: keep the dedicated reader/runtime identities least-privilege, apply only reviewed Supabase lockdown slices, then activate the Intelligence Materializer on bounded real prospects before any bulk historical write.
2. Activate the staged Phase 3E outbound/reply hardening migrations and inbound runtime under the existing production gates.
3. Activate Phase 3F outcome/revenue migration and dedicated runtime identities in OBSERVE first.
4. Send/deliver the first genuine governed buyer opportunity and capture real delivery/conversion evidence.
5. Recognize the first independently verified paid outcome as actual revenue and gross profit.
6. Feed the canonical Phase 3F outcome projection into Astra/Omega/revenue intelligence calibration.
7. Supabase-backed AI Closer production state-machine gate ✅ local/tested; activate its canonical migrations, separated runtime credentials and OBSERVE worker only under production gates.
8. Phase 4 Astra Operating Layer is CURRENT in OBSERVE/local-safe engineering mode; carry the first-revenue feedback loop as a production authority gate rather than an engineering blocker.
9. Continue Phase 5 organic intelligence and Phase 6 Agent Web/A2A capability execution in parallel where they do not bypass gates. Build the Search Intelligence foundation first; stabilize its API contract, then build the Search Command Centre frontend.
10. Expand Astra operating authority only after the genuine buyer → verified payment → outcome → feedback loop proves controls and economics.

11. BSC USDT smart-contract escrow: local contract + verifier + database rail ✅;
    canonical Supabase migration ✅; external audit, production identities and mainnet contract deployment pending.
12. Empire Intelligence Fabric: canonical schema + provenance/temporal graph ← ACTIVE SUPPORT WORK;
    integrate real source adapters and TAM segmentation while primary effort completes Phase 3F outcome/revenue feedback.

## Definition of Actual Revenue
Actual revenue requires independently verifiable payment evidence tied to a real buyer, real commercial terms and the relevant Empire request/order. Escrow funding is not revenue; a verified escrow release is only revenue-eligible until a separate governed accounting event recognizes it. Modeled, forecast, quoted, pending, simulated or manually asserted values are not actual revenue.
