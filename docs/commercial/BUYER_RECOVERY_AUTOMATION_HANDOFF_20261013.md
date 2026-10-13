# Empire AI — automated buyer evidence recovery and founder action desk

**13 October 2026 · OBSERVE · isolated and committed source candidate, not production loaded**

## Why this is the minimal integration
EmpireOS already has the authorised 30-minute buyer acquisition scout, buyer-network first-party site and due-diligence refresh, buyer qualification queue, enterprise contact sync, 2-minute deferred enrichment worker, founder review materialisation, reply reconciliation and Outbound Governor. Creating another scheduler, agent, CRM, database or external provider would duplicate the operating architecture and undermine first-party truth.

The current 2,136-record deferred queue had 2,051 candidates that the proposed evidence parking policy would hold without new evidence. Repeated unsuccessful probes have sometimes exceeded 1,000 attempts. The previously implemented isolated patch (commit `f40e8f6b`) prevents routine retries on evidence-exhausted records and preserves the ability for distinct same-host named-person or newly verified company contact-route evidence to wake a prospect, including when a worker held a lease. The canonical production queue has NOT been altered.

## Automatically performed after the buyer scout completes
The existing `scripts/run_buyer_acquisition_scout.py` invokes `scripts/run_buyer_network_evidence_cycle.py` within its current 30-minute schedule. The bounded read-only pipeline now adds a fourth and final stage:
1. Existing bounded first-party direct-site probe.
2. Existing first-party due diligence.
3. Existing private founder qualification action refresh.
4. NEW `scripts/build_buyer_recovery_action_desk.py --write --repo-root /srv/empire_os`: deterministic snapshot-to-founder-action triage.

The new stage reuses the durable `runtime/hunter/buyer_deferred_enrichment.json` and the existing queue's same-host evidence and retry-lane contracts. It does not crawl, requeue, claim work, refresh CRM contacts, send email, access secrets, change EmpireDB, call an external API, sign a contract, activate traffic, or move funds.

The packet is a private `0600` atomically written file:
`runtime/buyer_network_intelligence/buyer_recovery_action_desk_latest.json`.

Each high-priority research item contains: canonical prospect ID, business/domain, commercial priority, existing product hypothesis (NOT product readiness or buyer demand), retry/parking status, existing same-host person-evidence URLs to reverify (NOT a validated email), verified company-route *types* (no contact values), missing evidence and exact next research action. This is not an automatic sender list. The report is capped at 25 detailed rows with truthful full-population totals and truncated-report indicator. Two rows sharing a domain remain separate identities and their duplicates are called out, not merged.

The full source JSON is bounded, schema-checked and SHA-256 pinned across the analysis; concurrent source mutation fails closed. A source symlink, malformed/oversize data, or unsafe report destination blocks emission. No raw email contact values or secrets appear in the report or console output. The prior zero-authority commercial gates remain unchanged.

## Read-only test evidence
- 94 scoped tests passed, including 41 directly affected tests; tests cover source/identity integrity, false same-host claims, source symlink rejection, private output, loop safety, no outbound, duplicate domains, priority ranking, and worker lease / fresh-evidence wake.
- Production-source **read-only** report projected 131 high-priority records and 2,051 eligible for parked-policy status. Top product-matched candidates included Neighborly, TurnPoint, EQT, Blackstone Operating Team, Vista Equity Partners, Authority Brands and Apex Service Partners. These are still unqualified research targets.
- An isolated temporary-directory `--write` produced the packet with mode `0600`, and the canonical source JSON hash was unchanged. A production-path run without `--write` also retained the same queue SHA-256. Production output path was not created.
- This is code/test/isolated-source evidence; **NOT a claim of live automatic execution**.

## What remains outside permitted automatic authority
- The first-party professional `phil@mail.empire-ai.co.uk` / `reply@mail.empire-ai.co.uk` IMAP/SMTP credentials and sender configuration are not yet proved in production. Gmail connector activity in ChatGPT is not a first-party live inbox connection on the server.
- Nineteen October 13 Gmail send IDs were confirmed in Gmail but are NOT canonical EmpireDB outbound intentions by virtue of this report. No repeat sending without an exact live history and suppression check. The four older hard-bounce/block recipients remain no-retry pending controlled suppression reconciliation.
- Buyer appetite, procurement authority, exact person-bound contact, lawful purpose/source, commercial price/terms, signed agreement, funds, live USDT BSC settlement, fulfilment and revenue reconciliation remain separate.
- Fully self-sending outreach should only be enabled after the founder separately approves a **bounded standing policy** with explicit permitted persona, source, daily cap, domain exclusion/suppression, human escalation, owned transport, country/compliance and kill switch; this release does not grant such approval.

## Controlled release handoff
1. Review isolated branch `feature/buyer-evidence-park-20261013` commits. Do not overwrite the dirty production main checkout or other specialist worktrees.
2. Under separate exact release authority, reconcile/merge the bounded source + tests into the live main branch and run its scoped production-source regression.
3. Only under explicit activation/restart approval, load the updated source in the existing 2-minute enrichment service and existing buyer scout cycle. Do **not** create another timer or restart unrelated services.
4. Read back generated packet's schema/version, source hash, owner/mode `0600`, exact research counts and source/worker effects; prove NO sends/calls/payment.
5. Next independent revenue milestone: verify one person-bound, willing buyer and a product-specific scoped pilot; founder approves actual commercial send/terms/payment under the established gated loop.

**Status:** RESEARCH_AUTOMATION_CODE_COMPLETE / TESTED / NOT_PRODUCTION_ACTIVE.
