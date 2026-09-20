# Recovered Manus Pay-Per-Call Empire — Salvage Map

Date: 2026-09-20
Status: HISTORICAL DONOR SYSTEM — DO NOT MERGE WHOLE STACK

## Source identity

Recovered handoff describes the older `pay-per-call-empire` product: AI-powered
pay-per-call lead generation, lead marketplace, media buying, affiliate
operations, white-label, notifications and automation.

Its historical stack was React/Vite/Tailwind/shadcn + Express/tRPC +
Drizzle/MySQL/TiDB + Manus OAuth/hosting.

Current EmpireOS remains canonical:
- Python/FastAPI services;
- Supabase/Postgres canonical data;
- BSC USDT canonical payment rail;
- governed Resend outbound/reply capture;
- current Hunter/Omega/GTM/Closer/Revenue OS/Astra architecture.

Do not reintroduce the historical framework/database/auth stack.

## P0 — Salvage now for revenue

### 1. Governed follow-up sequence execution

Historical donor capabilities:
- emailSequenceService;
- leadFollowupService;
- outreach cadence/follow-up workflows.

Current EmpireOS already has:
- first-touch governed outbound;
- delivery events;
- reply capture/classification;
- outreach intelligence recommendations;
- cadence review;
- closer handoff.

Current gap:
- recommendation-only follow-up execution.

Target:
- reply-aware governed follow-up scheduler;
- no follow-up after positive/negative/opt-out reply;
- suppression-aware;
- bounded daily cap;
- evidence-backed recipient only;
- first touch and follow-up tracked separately;
- no duplicate first-touch;
- explicit expiry;
- existing outbound governor remains final send gate.

This is the highest-value donor capability because the commercial loop is now
waiting for genuine buyer conversation after delivered outreach.

## P1 — Salvage for production resilience

### 2. Kill switch and circuit breakers

Historical donor:
- killSwitchService;
- circuitBreakerState;
- operator System Health dashboard.

Current gap:
- no dedicated first-class kill-switch/circuit-breaker module was found in the
  active EmpireOS application surface.

Target:
- per-provider and per-lane circuit state;
- failure thresholds and cooldown;
- read-only Founder Console visibility;
- explicit emergency stop controls;
- no hidden global authority changes.

### 3. Realtime operator event stream

Historical donor:
- realtimeDashboardService;
- live channel subscriptions/events.

Current gap:
- no dedicated realtime dashboard service was found in the active application
  surface.

Target:
- Supabase realtime/read-model event stream;
- acquisition, outbound, replies, closer, payment, fulfilment, revenue and
  system-health events;
- Founder Console consumes evidence, never becomes the source of truth.

## P2 — Salvage for SaaS/productization

### 4. White-label/reseller portal expansion

Current EmpireOS already has `empire_os/whitelabel.py`.

Historical donor adds useful product-surface ideas:
- reseller branding;
- payout management;
- customer-facing portal;
- account-level white-label controls.

Salvage product/UX concepts, not old storage/auth code.

### 5. Import, deduplication and operator utilities

Historical donor:
- CSV/XLSX lead import;
- duplicate review/merge UI;
- benchmark dashboards;
- template browser/customizer;
- notification preferences.

Useful for SaaS/operator workflow after first-revenue proof.

## Already superseded — do not duplicate

### BSC USDT payment core

Historical donor contained:
- exact USDT amount intents;
- server-owned catalog;
- BSC chain verification;
- transaction receipt + confirmations;
- exact token/recipient/amount checks;
- idempotent fulfilment;
- transactional marketplace delivery.

Current EmpireOS already has:
- `empire_os/bsc_usdt_verifier.py`;
- `empire_os/bsc_payment_evidence.py`;
- `empire_os/payment_governance.py`;
- `empire_os/payment_role_transport.py`;
- governed BSC payment-request migrations;
- BSC evidence binding;
- escrow verification;
- payment DB tests.

Use the historical test matrix as a comparison checklist only.

### Media buying / advertising

Historical donor contained:
- ad performance;
- budgets;
- campaign orchestration;
- A/B testing;
- audiences/lookalikes;
- retargeting;
- creative assets;
- CRO;
- competitor intelligence.

Current EmpireOS already has a broad Advertising subsystem and media-buyer
agents. Salvage missing UX patterns only.

### Marketplace / affiliate / payout

Current EmpireOS already has marketplace, affiliate and payout modules.
Historical code is reference material only.

### AI scoring / voice / compliance

Current Hunter/Omega/Predictive/Conversation/Closer/Compliance architecture
supersedes the old implementations.

## Explicitly retired / incompatible

Do not revive:
- Manus OAuth/hosting coupling;
- MySQL/TiDB as canonical data;
- Drizzle as canonical migration layer;
- tRPC/Express as the EmpireOS backend core;
- buyer-facing Stripe/card flows;
- Twilio as canonical telephony;
- SendGrid as canonical outbound email;
- client-asserted payment success;
- old valuation/revenue claims without fresh evidence.

## Implementation order

1. Governed follow-up sequence execution.
2. Circuit-breaker / kill-switch layer.
3. Realtime Founder event/read stream.
4. White-label/reseller UX expansion.
5. Import/dedupe/operator utilities.
6. Compare historical BSC verifier test matrix against current BSC suite and add
   only genuinely missing cases.

## Anti-drift rule

The recovered Manus app is a donor system, not a second architecture.

Any salvaged capability must:
1. use current Supabase canonical evidence;
2. respect current BSC USDT payment governance;
3. use current GTM/outbound/closer gates;
4. preserve no-fake-data rules;
5. feed the current Revenue OS/Economic Memory loop;
6. become visible through the Founder Console where useful.
