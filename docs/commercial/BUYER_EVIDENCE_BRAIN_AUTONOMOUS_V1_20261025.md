# EmpireOS Buyer Evidence Brain — autonomous intelligence, governed execution
**25 October 2026 | Original EmpireDB + Buyer Scout + CRM | Read-only release candidate**

## Why this exists
EmpireOS already runs first-party company research and a governed Buyer Acquisition Scout, plus a 15-minute read-only Gmail evidence cycle. It must do the analysis itself rather than requiring ChatGPT to reopen each buyer thread and reinvent the same questions. Build is attached to that ORIGINAL system, not a duplicate daemon, database, Telegram bot, or CRM.

## Original pipeline, augmented
1. **Discovery:** the existing Scout probes first-party public company material and produces research candidates; a website claim is not buyer demand.
2. **Exact identity/contact and safety:** suppression/STOP, original canonical outbound-intent reader, source rights, and recipient binding remain mandatory; this build creates no send permission.
3. **Inbound email evidence:** the original read-only Gmail discovery requires a two-way, sender-aligned buyer thread; the parser now recognises these three distinct reply-only observations:
   - `PUBLISHER_ACCEPTED_OUTCOME_PILOT_REPORTED` (buyer-side publisher reports a pilot approach works)
   - `PUBLISHER_REVENUE_SHARE_TARGET_REPORTED` (publisher stated negotiating target, not agreed rate)
   - `PUBLISHER_SIGNED_TERMS_AND_COVERAGE_REQUIRED_REPORTED` (publisher says no live activity before signing and verified coverage)
   Each code links back to exact Gmail message ID and observation time. Raw email text is not copied to runtime snapshots, and quoted older text is excluded.
4. **Reconciliation:** original `import_connected_gmail_buyer_metadata.py` preserves a bounded list of the latest authenticated inbound publisher signals for already-found, previously unlinked new-domain threads. Original `commercial_relationship_registry.py` validates the shape. Original `reconcile_buyer_email_relationships.py` classifies traffic-supply hypotheses and puts proof tasks in the existing founder report.
5. **Capacity proof:** the new `buyer_evidence_brain.py` reads the existing `runtime/buyer_capacity_readiness/latest.json` through the original executive capacity verifier. Missing, stale or untrusted data can never become a specific contracted installer buy box.
6. **Next work, not imaginary sales:** when a genuine publisher expresses interest, the next work item is `VERIFY_ONE_CONTRACTED_INSTALLER_BUYBOX_AND_PRICE`, with explicit requirements for signed installer contract, verified MCS and postcodes, payable event, accepted buyer payment, costs/margin, settlement/disputes, and consent. A provider's negotiating target is not an activated opportunity or revenue.
7. **Learning:** actual accepted/rejected scopes, payables, refunds and settlement only flow into canonical EmpireDB through independently authorised existing outcome modules. This code does not implement any new financial recognition or trust unknown fields.

## Real observed example (not synthetic lead data)
Connected Gmail message `1a159bed9fcc61ac` from SolarBriton marketing/finance dated 20 October 2026 proposed a 30-day publisher referral pilot, 70% of the received installer fee (target, not contracted), £35 floor per accepted event, and no activation pending signed terms and independently verified installer coverage. The founder's reply `1a15a5e4391ef516` already acknowledged this on 20 October. Current buyer capacity snapshot `2026-10-25T21:41:02Z` had 1,057 recorded buyers but ZERO capacity verified, ZERO terms verified, ZERO fully activated. Hence one downstream paying buyer is the genuine next step, NOT more generic cold outreach or a claimed profit forecast.

## Execution and release boundaries
- The existing `empire-buyer-gmail-evidence.timer` remains authoritative; no new timers, services, root-run code, payment gates or provider OAuth changes.
- Read-only `scripts/run_buyer_gmail_evidence_cycle.py` already calls Gmail poll, bounded importer, and reconciler in that order. Deploying these changes through the approved original release channel attaches the engine to that chain; simply committing them does NOT update the live worker.
- Strict invariants: `OBSERVE`, `OUTBOUND_ENABLED=0`, no direct Gmail send, no CRM writes, no trade or payment execution, no synthetic commercial evidence, no price quotes without exact buyer contract.
- No automatic second mail after SENT, bounce or explicit opt-out; no bypass of mail-service safety checks. Named buyer replies trigger **draft/review** work, not unrestricted sending.
- Production change review must compare only these touched modules against the running checkout and retain a verified rollback. No overwrite of unrelated dirty working files or a protected mailbox cycle.
- Known limitation: discovery is bounded to recent sent two-way threads, and older conversations stay in scope only when source-linked by the original metadata reader. Without a genuine new source scan, the pre-release snapshot has not yet gained the new signals. This is a code-path readiness test, not proof that full downstream payments are operational.

## Verification
Targeted regression suite includes `tests/test_publisher_commercial_brain_20261025.py`, `tests/test_buyer_mail_semantics.py`, `tests/test_connected_gmail_buyer_metadata.py`, `tests/test_buyer_thread_discovery.py`, `tests/test_buyer_gmail_evidence_cycle.py`, `tests/test_affiliate_referral_role_classification.py`, `tests/test_commercial_outbound_holds.py` and the existing executive capacity tests. A live-input read-only preview against canonical runtime snapshots must return no new sends, no money and `NO_VERIFIED_COMMERCIAL_CAPACITY` until real proof exists.
