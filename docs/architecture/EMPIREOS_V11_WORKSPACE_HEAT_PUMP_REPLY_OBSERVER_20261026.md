# EmpireOS V11 — four original Workspace heat-pump threads in existing buyer evidence cycle

**26 October 2026 | review-only branch, no deployed release**

## What was missing

The original `empire-buyer-gmail-evidence.timer` polls an older personal-Gmail buyer cohort and schedules its existing optional Workspace observer. The Workspace solar observer covered six previous solar sends in its integration base. The newer **C12 Energy, BB Heat Pumps, Q Smart and ARC Climate Solutions** messages were sent from the authenticated Workspace account, not the personal-Gmail account. Those four exact threads were not in the original fixed monitoring cohort.

This change **does not create a new Gmail account, OAuth client, service, systemd timer, sender, CRM, database, buyer, agent or payment route**.

## V11 scoped implementation

- `empire_os/workspace_heat_pump_reply_tracking.py`: a pure metadata-only reviewer of four pre-existing Gmail thread IDs, each anchored to the exact original sent-message ID; the same `GoogleWorkspaceMailboxProvider` must verify the authenticated Workspace account first.
- The reviewer validates complete four-thread responses, original sent labels/identity, exact thread/message association, bounded timestamps and identities. Potential replies must follow the original send, be addressed to a configured Workspace recipient and match the original recipient or its email domain. Same-domain colleagues remain unqualified candidates; no inferred buyer authority.
- Stores only known company name, exact Gmail IDs, timestamp and structural RFC ancestry, not message bodies, snippets, subject lines, raw MIME or email addresses.
- `newly_observed_heat_pump_candidates` uses a private 0600 metadata snapshot. An unchanged candidate produces zero new events; dropping a previous candidate or changing a sent anchor fails closed.
- `scripts/poll_workspace_solar_outreach_readonly.py` invokes this **optional** cohort through its existing Workspace service. Heat-pump failure is reported separately and does not erase or halt the historical solar cohort. No automatic replies, CRM promotion, queue action, outbound, settlement or training.
- The new source is NOT part of the personal Gmail `THREADS` mapping. Do not insert Workspace IDs into the personal OAuth reader.

## Evidence and remaining release conditions

The connected Workspace mailbox was read in ChatGPT on 26 October 2026. All four selected threads had exactly one sent message at that point; no inbound reply or signed buyer acceptance was observed in those exact threads. This is not an exhaustive account-wide inbox audit.

Isolated synthetic tests cover four-anchor acceptance, duplicate/wrong/absent original sends, exact/same-domain reply candidates, wrong sender/routing, missing proof, replay idempotency, historical snapshot rollback/replay rejection and graceful optional failure. The integration branch and original production checkout are intentionally separate.

**No production deployment.** Production's Workspace observer contains additional priority-payer changes not present in the V10 review base. Before any merge, the original mailbox owner must reconcile that drift and preserve those previously existing functions. The protected CRM owner's login-security changes and pending tenant-RPC approval remain outside this patch. Live external Workspace polling and private snapshot writes were not invoked from this branch: the provider may renew its original OAuth token during `_service()`, which is intentionally not part of the isolated tests.

Even an authenticated email reply is NOT binding commercial acceptance, recipient capacity, an accepted order, independent delivery, payment or Economic Memory authority. The next real gate is a genuine buyer response with terms, geography, eligible lead definitions, provider verification, accepted delivery, settlement and a complete reversal record.

## V11.1 — owner's live Workspace and scheduling reconciliation

The original production Workspace observer had a separate uncommitted, owner-authored **two-thread priority-payer** module. Its baseline was byte-identical to the V11 base. The owner-authored code was copied into the **isolated candidate** with SHA-256 `b3b217c51904cf6bb7aaddb724af0778c57ca1da2944f0ede2aa86734b8e63bd` without modifying the owner's original file. The original priority monitor and V11's four heat-pump monitors now share the same authenticated Workspace client and independent private snapshots; the six historical solar threads remain unchanged.

The existing 15-minute `scripts/run_buyer_gmail_evidence_cycle.py` did **not** call the exact Workspace follow-up reviewer, even though separate buyer-acquisition code could call it. V11.1 adds that reviewer to the **existing OPTIONAL_STEPS**, after the existing sent-domain receipt step, without new timer, queue or sender. An outage remains `HELD` and does not block the historical buyer reconciliation.

An authenticated, non-writing live Workspace check from the combined isolated checkout observed six historical solar sent anchors, two priority payer sent anchors and four heat-pump sent anchors; **zero inbound heat-pump reply candidates**. No buyer acceptance or payment can be inferred. Tests on the merged owner-preserving branch passed **125 cases** (one existing deprecation warning). This release does not alter CRM security, restricted tenant SQL, fulfilment, bank settlement, outbound permissions or model training. The corresponding scoped production deployment must retain exact pre-change hashes, protected backups, original timer configuration and immediate rollback capability.
