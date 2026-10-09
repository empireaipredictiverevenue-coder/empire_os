# Revenue priorities — qualification and owned-mailbox send freeze

**Scope:** evidence-led buyer discovery, founder-reviewed qualification, and fail-closed email sending while the Empire AI owned professional mailbox is not provisioned. No new timer or separate agent system was created.

## Work completed

- Existing buyer discovery, review, deferred enrichment, enterprise contact and direct-site evidence timers remain enabled. They refresh on their own cadence; do not duplicate their crawls or restart them just to refresh a dashboard number.
- `scripts/build_buyer_qualification_actions.py` reads four existing EmpireOS buyer-network snapshots and creates a deterministic, bounded founder-review/evidence-recovery plan. It has **no network/DB/email/call dependencies**. Each record lists the actual missing commercial evidence and the exact next verification question. It never promotes a website or generic contact signal into a verified buying intent.
- The operator command `./.venv/bin/python scripts/build_buyer_qualification_actions.py --write` atomically saves a private mode `0600` report to `runtime/buyer_network_intelligence/founder_qualification_actions_latest.json`. Without `--write`, it prints a bounded summary and does not mutate runtime. Counts will change as existing scouts run; source hashes protect against inconsistent concurrent reads.
- The existing `founder_review_packets_latest.json` remains the authority for *founder review only*. A "trusted" founder-review packet is **not** an authorization to send, a verified buyer conversation, an agreed payout, or evidence of realized revenue.

## Documented safety controls

- The scheduled `scripts/outbound_governor_worker.py` cannot derive sending authority from a legacy Resend API key. With no owned professional mailbox transport, `--execute`, GUARDed mode and auto-send/approval flags degrade to **OBSERVE**; no database approval, outbound claim or send event is executed by that worker.
- Manual `scripts/outbound_email.py --send` fails before creating an outbound database claim. Read-only intent review remains possible if its database credentials are independently available.
- `empire_os.outbound_provider.send_with_resend` rejects real third-party Resend network sends; test-only injected provider doubles can still exercise the parsing and idempotency contract without external calls.
- The historical `empire_os.agents.lead_deliverer_agent.send_email` direct bypass now returns `(False, 'owned_mailbox_outbound_disabled')`, rather than sending via Resend or logging an undelivered email as successful. A separately edited unrelated EmpireDB terminology line in that file was intentionally **not included** in this change.
- Founder mailbox live readiness is still `CONFIGURATION_REQUIRED`, and the existing reply identity bridge has not proven authenticated buyers, canonical message identity or original outbound intent. Reply verification remains gated; no inbox or customer data were altered.

## One clear commercial target

For the next controlled founder review, inspect `runtime/buyer_network_intelligence/founder_review_packets_latest.json`. This may contain a first-party-correlated company such as `paymyreferral.com`, but it must remain review-only. Before any commercial offer or approved outbound, determine active publisher acceptance, actual payout economics (currency/unit/validation/terms), jurisdiction-specific consent, integration and a canonical person-bound contact route. Do not infer fees, ROI, reply intent or revenue from marketing pages alone.

The broader shortlist may contain `VERIFY_REQUIREMENTS` records needing first-party payout, compliance, tracking and application evidence. The report ranks those evidence gaps, not lead volume, by importance. No buys, paid traffic, phones, bulk email or external lead subscriptions are required for this stage.

## Stop criteria / no looping

**Engineering:** once the focused buyer/outbound/reply regressions pass and one private qualification report is saved, mark these scoped tasks DONE. Do not revisit IMAP or add new mail engines while the owned mailbox has not been purchased/provisioned.

**External dependency:** after the founder obtains legitimate owned mailbox credentials, verify the installed read-only Founder API via `./.venv/bin/python scripts/verify_owned_imap_mailbox.py --service-probe` and separately establish authorized owned SMTP/sender, verified suppression and canonical reply binding. The user must explicitly authorize any future changes to live outbound execution; the current freeze must not auto-lift merely from presence of IMAP credentials.

**Revenue:** a first genuine, authenticated, person-bound buyer conversation requires real inbound, original outbound-intent linkage, consent/suppression and human/founder review. A sent or drafted message, website sign-up link, reviewed prospect, or simulated reply does not meet that criterion.
