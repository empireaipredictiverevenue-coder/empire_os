# Empire AI — Wolfgang reply: verified content and bounded recovery

14 October 2026. Founder mailbox recovery, production truth first.

## Original provider record recovered

The connected Resend receiving account returned the original email ID 44a5aec3-bb34-47c5-8a89-ab1eaeee0607 on 14 October, originally received 23 September 2026 00:48:08.417 UTC. Sender wolfgang@tarrytownroofing.com, to reply+c77e459a-c3a9-4b0a-962a-e52c0f728bd9@mail.empire-ai.co.uk, subject 'Re: James — quick idea for Tarrytown Roofing'.

**Original new reply text is precisely 'Stop'.** The remainder contains an email signature and quoted outreach. It must be treated as an explicit unsubscribe, not a buyer conversation. No response to Wolfgang is authorised.

Source evidence is verified using the user's connected receiving-account read-only API, independently of the canonical EmpireDB webhook metadata. The local server stored a placeholder and has not yet been updated. The original 23 September exception was swallowed by earlier code, so the exact historical API error cannot be reconstructed.

## 14 October recovery failure diagnosed from PostgreSQL logs

The first approved one-record repair returned `CANONICAL_LOCAL_POSTGRES_PROBE_FAILED`. A bounded read of the local PostgreSQL error log establishes the **actual** database failure: `pinned provider reply evidence mismatch` raised from the transaction's guarded `DO` block, with the transaction rolled back. It was not a PostgreSQL connection outage. The original preflight allowed canonical `classification='unsubscribe'` and/or `intent_status='suppressed'` but the atomic update insisted on `classification='unclassified'` and status in `sent/delivered/replied` only. If another workflow suppressed the record, this would cause a false rejection; the exact live classification/intent state was not disclosed by the failed run.

The revised recovery mirrors all preflight conditions inside the transaction. It accepts a preclassified canonical unsubscribe **only if the email suppression record already exists**, permits an intent already in `suppressed` state, and skips duplicate classifier/event writes when both are already suppressed. It remains pinned to the same sender/recipient/subject/provider/date/body placeholder and performs an exact post-commit check requiring `body='Stop'`, `classification='unsubscribe'`, `intent_status='suppressed'` and confirmed suppression. Null-safe comparisons guard identity checks. Future PostgreSQL errors are reported by sanitized SQLSTATE (`READ_ONLY_EVIDENCE` versus `ATOMIC_RECOVERY` versus `POSTCOMMIT_READBACK`), never raw SQL or credentials. Custom `P1001`, `P1002` and `P1003` distinguish exact identity, missing-body marker and opt-out state mismatches.

## First-party engineering changes

- `empire_os/outbound_provider.py` now classifies historical-style failed `Receiving.get()` exceptions into a small allowlist of safe status codes (401, 403, 404, 429, 5xx, network or unknown) without logging exception text, secrets or message bodies.
- `empire_os/resend_webhook_app.py` stores that safe error code in inert canonical reply metadata for future signed inbound webhook records. No agent or outbound action is enabled.
- `scripts/recover_single_tarrytown_stop_20261014.py` implements a one-time, root-gated, exact-record recovery of the **unquoted visible response only** ('Stop'); it does not store the provider HTML, signature, attachments or quoted email in the database. The expected canonical reply ID, intent ID, sender, recipient, provider message ID, date, subject and missing-body marker must ALL match. It uses the existing `empire_reply_ingest` role and `classify_outbound_reply` function to classify and suppress the same canonical recipient. It performs a post-commit readback and is idempotent.
- The one-time recovery also probes the local server's currently configured receiving API key using a GET for the exact provider message, without printing the token or message text. Failed local key probes are reported as sanitized status codes; they do not negate the separately verified connected-account provider evidence. A **conflicting** successful provider record causes a hard hold.
- A mismatched original outreach recipient, a changed reply, or an already partial recovery causes a hard hold. No other reply, table row, company/domain suppression, recipient, mail service, DNS or payment is modified.

## Activation

**Not yet applied**. Default one-time operator actions:

Read-only (root required):

    sudo -n /srv/empire_os/.venv/bin/python -m scripts.recover_single_tarrytown_stop_20261014 --review

Founder-approved one-time canonical recovery:

    cd /srv/empire_os
    sudo -n ./.venv/bin/python -m scripts.recover_single_tarrytown_stop_20261014 --apply --approved-wolfgang-stop-only

Expected exact status: WOLFGANG_STOP_RECOVERED_AND_SUPPRESSED.

The inbound webhook service must subsequently be restarted in a separately verified controlled step to load the new safe diagnostic codes; this code commit alone does not alter running services. Do not blindly rotate existing API credentials or MX records.

No emails have been sent or provider accounts changed. Outbound Governor remains OBSERVE.
