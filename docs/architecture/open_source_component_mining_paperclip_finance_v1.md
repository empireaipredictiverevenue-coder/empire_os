# Open-Source Component Mining — Paperclip + FinanceSkills v1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT / OBSERVE-FIRST
Programme: EmpireOS Full Completion

## Purpose
Component-mine two upstream open-source projects without replacing canonical EmpireOS owners:

1. `PaperclipAI/paperclip`
   - target value: agent task checkout, persistent state, budgets, approvals, audit, heartbeat/routine patterns, multi-organisation isolation, cost controls;
   - canonical Empire owners remain Astra, Department Work Queue, Agent & Tool Execution Plane, Control Fabric, Founder Console.

2. `GAJETOso/financeskills`
   - target value: reusable finance/accounting/audit/compliance skill patterns;
   - canonical Empire target is a governed Law Firm Finance Intelligence capability, not a generic finance agent.

## Law-firm target capability
Potential governed outputs include:
- matter/client profitability review;
- WIP / AR ageing and collections intelligence;
- cash-flow and collections forecasting;
- acquisition-cost vs expected-fee economics;
- budget/variance analysis;
- finance anomaly/reconciliation review;
- settlement/cash forecasting;
- legal-enterprise finance dashboards.

Client-money/trust-accounting, legal privilege, regulatory compliance and jurisdiction-specific accounting controls remain explicit evidence/architecture gates. No upstream skill is trusted as sufficient for those controls without Empire-specific verification.

## Non-replacement rule
- Paperclip must not replace Astra, EmpireOS, Execution Plane, EmpireDB, JEV, Marketplace/Auction, Revenue Exchange, Economic Memory or Founder gates.
- FinanceSkills must not become canonical accounting truth by itself.
- Upstream code is never installed into production during component mining.

## Authority
Observe/component-mine only until a separate implementation slice is independently approved and verified.

Forbidden in this slice:
- production install/deploy;
- client or privileged matter data;
- outbound;
- commercial terms;
- payments/funds;
- revenue recognition;
- authority expansion;
- direct upstream dependency without license/security review.

## Required outputs
### Paperclip mining agent
Produce a component map with:
- upstream capability;
- EmpireOS equivalent/owner;
- duplicate vs additive classification;
- integration pattern worth copying;
- files/interfaces that would need changes;
- security/ACL/multi-tenant concerns;
- cost/budget/approval implications;
- recommendation: ADOPT_PATTERN / REIMPLEMENT / INCUBATE / REJECT.

### FinanceSkills mining agent
Produce a skill map with:
- upstream skill/category;
- law-firm enterprise use case;
- required input evidence;
- output contract;
- jurisdiction/compliance caveat;
- Empire owner/consumer;
- deterministic calculator opportunity;
- tests/evals required;
- recommendation: ADAPT / INCUBATE / REJECT.

## Progress rule
Each agent result must be persisted before any implementation work begins.
No upstream component advances to IMPLEMENT without a separate architecture delta and non-overlapping lease.
