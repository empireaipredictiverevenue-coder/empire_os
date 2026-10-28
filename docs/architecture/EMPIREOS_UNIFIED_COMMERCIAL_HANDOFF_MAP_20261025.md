# EmpireOS — One System, End-to-End Commercial Cohesion
**25 October 2026 | Original EmpireOS, EmpireDB, Smart CRM, JEV, Astra, Economic Memory**

## Why this change is needed
The live EmpireOS environment already runs multiple OBSERVE agents/timers. However, a company discovered by Buyer Scout does not automatically prove a consented opportunity; an engaged publisher cannot be priced until a specific downstream buyer has agreed to buy; a payment aggregate cannot be assigned to a tenant/customer without one canonical receipt chain. Copying counts into the same dashboard would conceal these gaps.

This release candidate **adds a cross-system view to the existing `revenue_completion_supervisor`**, which already runs through the original `empire-revenue-completion-supervisor.timer`. No second supervisor, schedule, database, CRM, bot or outbound service is introduced.

## Current actual evidence (not sample projections)
Read-only inspection of canonical existing private runtime snapshots on 25 October 2026:
- Buyer Scout **10 research candidates**; JEV **59 observations**. Neither represents 10/59 qualified commercial prospects.
- Opportunity Factory **21 candidate research items; zero factory ready**.
- Original Gmail registry **five warm relationships**; these are not five purchase agreements.
- Canonical capacity reader **1,057 buyer rows; zero fully commercially activated**.
- Predictive Revenue **218 context candidates; zero passed**. These are not customer orders.
- Orders/Payments **zero real observed payments**; Revenue Pulse **zero recognised revenue cents**.
- Economic Memory **zero outcome-conditioned memories**. Episodic agent successes are not financially proven outcomes.

The numbers measure **different populations** and MUST NOT be summed or converted into a funnel denominator without canonical entity IDs and provenance.

## Twelve dependent gates with original owner
| Stage | Existing owner | Minimum independent proof before stage promotion |
|---|---|---|
| DATA | Buyer Scout / JEV | Provenance, collection rights, observed timestamps |
| SOURCE_RIGHTS | Source Authorisation | Rights/consent for exact source and intended use |
| OPPORTUNITY | Opportunity Factory | Real relevant demand, observed scope and exact source evidence |
| PERSON_COMPANY | Identity Resolution / JEV | Canonical legal company / decision maker binding and provenance |
| TENANT_CRM | Original Smart CRM | Original EmpireDB tenant, founder access, authorised customer/company binding |
| BUYER_ACCEPTANCE | Buyer Acquisition | Named buyer, verified buy box, capacity, terms and approved acceptance rules |
| APPROVED_OUTBOUND | Buyer Reply Operations | Opt-out and suppression clear, sender authority, content approved for one recipient |
| ACCEPTED_ORDER | Revenue Ledger | Signed/accepted customer terms and exact attributed order event |
| SETTLEMENT | Payments | Independent settled transaction receipt and order linkage (USDT/BSC if the agreed permitted rail) |
| FULFILMENT | Fulfilment | Verified delivery and any return/dispute/acceptance window |
| REALISED_REVENUE | Revenue Accounting | Settled, attributable and recognised amount net of valid reversal/refund |
| ECONOMIC_MEMORY | Cortex / Economic Memory | Non-synthetic causal outcome reference; calibration labels not agent job DONE status |

A **canonical source-to-outcome identity** must be carried unchanged through these stages: source evidence ID, legal company/business entity ID, tenant ID, opportunity ID, customer/buyer authority, offer/order ID, accepted event, settlement ID, fulfilment/outcome ID, and causal memory reference. Preserve original source URL/observation time; no guessing from company name/domain, no recycled cross-tenant identity.

## What is actually wired in this release candidate
- Original `revenue_completion_supervisor.build_snapshot()` gains `cross_system_cohesion`, a bounded read-only projection over **nine existing source artifacts**.
- Every source must match its exact schema, OBSERVE mode, a recent timestamp, and non-executing authority. Wrong schema, stale data, unsafe flags, oversized files and symlinks do **not** count as evidence.
- The projection assigns current missing proofs to **existing** owners (Scout, JEV, Opportunity Factory, Buyer Acquisition, Smart CRM, Revenue Ledger, Economic Memory). It does NOT enqueue work, create privileged tasks, send emails or mutate EmpireDB.
- All 12 handoff gates remain unverified at *entity level* until linked original canonical receipts exist. Healthy service timers do not prove customer conversion.
- The separate, tested Buyer Evidence Brain review PR #111 can later populate `buyer_evidence_brain` inside the existing email registry; this projection detects that source only after controlled release. It does not misreport that PR as already live.
- Original Smart CRM has no supported independent tenant-authority snapshot in this read model; CRM must be attested through its existing authenticated EmpireDB reader and founder login. A file named CRM status is not enough.

## System autonomy boundaries
**Autonomous now via the original timers (where active):** source scouting, bounded research, evidence refreshes, conservative recognition of observed signals, queue prioritisation and read-only analytics.
**Still needs release verification:** Buyer Evidence Brain code and this whole-system supervisor addition are committed to isolated review worktrees, NOT part of production timers until the permitted release channel updates the protected working tree.
**Must stay explicitly gated:** binding offers, cold outreach/send, suppression overrides, identity/consent decisions, CRM tenant writes, funds, chain/mainnet, credit, live trade, commercial fulfilment and recognition.

The next closed-loop engineering increment should be an **approved original EmpireDB canonical handoff contract and receipts**, where the existing agents update the *same* opportunity state with source+tenant+owner evidence, not copy records into independent agent ledgers. Migrations 066–071 remain held until authorised real company data and owner approval.

## Verification and rollback
- Run `tests/test_cross_system_cohesion_20261025.py` and existing commercial-loop/revenue-pulse/economic-memory/supervisor tests.
- Read-only invoke the same `build_snapshot()` against production runtime with the worktree code, showing 9 source states, 12 stage holds, zero writes/sends, and the original supervisor result.
- Review only the two changed/new modules plus tests/docs for this addition; do not merge unrelated live working changes.
- Existing systemd timer/unit remains unchanged, and rollback is the original code for `empire_os/revenue_completion_supervisor.py` and removal of the new read-only helper. No DB rollback or financial reversal necessary because none is written.
