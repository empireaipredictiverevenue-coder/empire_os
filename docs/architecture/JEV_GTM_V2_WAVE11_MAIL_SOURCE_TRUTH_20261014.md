# JEV GTM V2 — Wave 11 First-Party Mail Route Production-Truth Gate

Date: 2026-10-14
Isolated worktree: `/home/ubuntu/empire_worktrees/jev_gtm_v2_20261014`
Branch: `feature/jev-gtm-v2-20261014`
Starting commit: `f56697b3`
Mode: OBSERVE, read-only; no production service changes, no DNS writes, no migrations, no outbound, no wallet or payment actions.

## Reason for wave

Wave 10 introduced a **verifier** for externally signed first-party SMTP ingress observations. That is not a mail receiver, an audited signer or proof of provider delivery. Production truth had to be verified before interpreting any RFC/IMAP candidate as a real buyer's reply.

On 2026-10-14 the explicit safe diagnostics from EmpireOS showed:

- `empire-gmail-relay.service`: active, `/health` provider `gmail_api`, mode `OBSERVE`, `send_authorized=false`, `mutation_authorized=false`, `oauth_verified=false`, `mailbox_ready=false`.
- `empire-resend-inbound.service`: active. Loopback health on :8097 reports `provider=resend`, `mode=OBSERVE`, `reply_transport_configured=true`. The code at `empire_os/resend_webhook_app.py` authenticates Resend Svix webhook signatures and can write via the existing restricted `empire_reply_ingest` RPC. A signed **Resend** webhook is not a signed receipt from Empire's own independently audited SMTP ingress.
- `empire-founder-dashboard-api.service`: active. Read-only `/v1/founder-mailbox/readiness` reports `provider=owned_imap`, `configured=false`, `status=NOT_CONFIGURED`, `suppression_evidence_complete=false`. No live mailbox messages were read.
- Existing `empire_os/empiredb_founder_reply_mailbox.py` and `scripts/deploy_founder_canonical_reply_view.py` in the production repository provide a **prepared**, reversible, root/approval-guarded read-only canonical reply viewer. The specific canonical viewer drop-in `/etc/systemd/system/empire-founder-dashboard-api.service.d/30-canonical-reply-view.conf` and protected reader credential `/etc/empire/founder_reply_reader.dsn` were **ABSENT**. We did not execute the release.
- Actual DNS answer: `empire-ai.co.uk MX 1 smtp.google.com.` while `mail.empire-ai.co.uk MX 10 inbound-smtp.us-east-1.amazonaws.com.`. Reply-subdomain SES routing and active Resend webhook cannot be assumed to constitute a single verified original-message receipt chain.
- No listener on usual local SMTP/IMAP ports was identified in the bounded process socket check. This does not prove that no external legitimate receiver exists; it does prove we did not observe a local first-party receiver on those checked ports.
- Production HEAD is changing concurrently in other agents' work, and branch isolation must be maintained.

No live outbound was attempted; no OAuth token, credential, email header/body, original personal information, tenant row or wallet content was printed.

## Wave 11 implementation

### Pure capability and authority check

`empire_os/jev_gtm_mail_source_truth.py`

- `assess_jev_ingress_truth` accepts only caller-injected safe health metadata, exact public DNS MX result strings, optional release-file presence booleans and bounded probe-failure labels.
- Returns an OBSERVE HOLD packet with split source truth for Google relay, reply MX external SES, Resend webhook, live Founder mailbox provider, canonical view activation, credential/drop-in *presence only*, and a deterministic ordered list of release blockers.
- No inherited trust of `provider` strings as proof of a first-party transport; valid signed provider events alone do not prove buyer intent or tenant/contact authority.
- `independently_verified_buyer_replies=null`, `verified_commercial_revenue=null`, `first_party_inbound_transport_verified=false`, `outbound_authorized=false` always; unknown probes result in UNKNOWN flags, not fake zero replies.

### One-hit operator probe

`scripts/probe_jev_mail_ingress_source_truth.py`

- Default without `--live-readonly`: no network/DNS or runtime files inspected; returns `LIVE_READONLY_NOT_REQUESTED`.
- Explicit `--live-readonly`: reuses **existing** `scripts.verify_founder_mail_end_to_end_readonly.local_get` and `_lookup_dns`, with fixed loopback GETs at 8775, 8766 and 8097 and fixed public DNS MX names. No custom receiver, OAuth credential inspection, provider mutation, mailbox fetch or database session.
- Separately checks only file **presence** (never opens content) of the already-prepared canonical reader release drop-in and private credential path.
- Sanitises all probe exceptions, returns a nonzero exit status for HOLD, and produces only safe public facts and release codes. It does not change systemd, run deployments or rotate mail DNS.
- One explicit live probe executed from the isolated branch. It returned `HOLD_FIRST_PARTY_REPLY_ACTIVATION` and the observed SES/Resend mismatch, disabled Gmail relay sends, inactive canonical reply viewer and absent release files. This is a snapshot; it must be rerun after another agent changes production.

### JEV decision review attachment

`empire_os/jev_gtm_mail_release_gate.py`

- `attach_jev_ingress_release_gate` binds only an exact OBSERVE HOLD truth packet to the trusted JEV V2 decision fingerprint, with a strict field policy prohibiting made-up verified replies, payments, consent, production changes or sending.
- Produces reviewable blocker codes but **never** changes the original JEV action or its buying score, canonical CRM, suppression, model calibration or contact status.

### Existing founder dashboard

Founder `/v1/founder-jev/status` includes three truthful static flags:
- mail ingress source-truth code implemented;
- **the API does not automatically perform a live topology check**;
- live first-party ingress remains unverified.

`apps/search-command-centre/src/app/founder/jev/page.tsx` displays the distinction. No new live public endpoint, timer, agent, mail sender or database role.

## Tested release condition

Targeted unit tests `tests/test_jev_gtm_mail_source_truth.py` and `tests/test_jev_gtm_mail_release_gate.py` reject:
- missing or malformed DNS data, excessive/untrusted health input;
- falsely active `ok: 'true'` string values;
- provider names pretending to prove original SMTP receipt;
- unproven canonical reader grants;
- forged JEV readiness, invented buyer counts, claims of deployment, DNS change, data reads or outbound sends;
- leaked provider exceptions or private values.

Existing founder mail diagnostic test suite reused; no new transport implementation created.

**Final independent verification:** 736 JEV/CRM/mailbox/Conversation OS/search/founder tests passed, 10 subtests passed, zero failures, one existing AnyIO/Starlette deprecation warning. Frontend `tsc --noEmit --incremental false` passed. Python source compile and `git diff --check` passed. The live one-hit bounded preflight also returned HOLD with the SES/Resend mismatch and inactive canonical view; no messages were read.

## Next exact operational milestones — no unsafe shortcuts

1. **Reconcile live delivery topology with current mail owner**. Establish the actual authoritative receiving MX and inbound provider before any DNS cutover. Preserve live delivery: no MX switch or service stop until a safe replacement path and end-to-end test are available.
2. **Respect sovereignty preference**. If fully first-party ingress is required, implement or commission an independently audited own receiving service with original SMTP delivery log, DMARC/SPF/DKIM trust boundary, raw-message digest protection, replay/idempotency controls, bounded retention and signed provenance. Wave 10's verifier can then consume those receipts; the signer must never run as the JEV public read API.
3. **Activate existing canonical reply viewer only under its own separate explicit approval** and only after privileged role checks and rollback proof. That viewer is a *recorded canonical reply reader*, not the authenticated original SMTP receipt.
4. **Approve migration 051 separately** before using its exact tenant-restricted JEV candidate RPC in production.
5. **Prove current inbound real records separately** via the existing controlled owner and prevent double-counting or provider crossover. Reconcile canonical tenant/person, original provider transport, suppression and opt-out handling.
6. Only thereafter independently label first real buyer conversations, founder-reviewed message actions and verified payment outcomes, then compare JEV's effect with the deterministic baseline.

The outcome is **a proven, executable fail-closed production-truth gate**, not a claim that real buyer conversion or a fully sovereign mail receiving service is live.
