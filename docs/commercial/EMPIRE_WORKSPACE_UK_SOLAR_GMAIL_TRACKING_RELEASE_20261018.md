# EmpireOS — Empire Workspace six-thread Gmail tracking bridge

**18 October 2026 | Existing six real Gmail sends | Non-sending, read-only evidence bridge**

## Root cause confirmed

The original `scripts/import_connected_gmail_buyer_metadata.py` and
`scripts/poll_buyer_gmail_readonly.py` are explicitly scoped to **flavag83@gmail.com**
and bounded Lead Smart/LeadBank/Validated/Connexis/Inquirly threads. Our six new
UK solar business emails were actually sent from `phil@mail.empire-ai.co.uk`
through the connected **phil@empire-ai.co.uk Workspace Gmail** account.
Appending these six threads to the personal buyer index would query a different
mailbox, incorrectly mix source identity and risk losing or inventing reply evidence.

The pre-existing `empire_os.google_workspace_mailbox.GoogleWorkspaceMailboxProvider`
authenticates the exact Workspace mailbox identity and supports a Gmail READ
scope, but its **live provider readiness reported `configured=False`** on
18 Oct 2026; the owned IMAP fallback also reported `configured=False`.
Neither may be bypassed with the personal Gmail credentials. No new token,
plugin, inbox, OAuth grant, SMTP gateway, worker/timer or database role was created.

The existing ChatGPT Commercial & PR Reply Watch already checks both connected
Gmail accounts hourly, read-only. The new server code does **not** duplicate that
automation and cannot truthfully assert that watch delivered any notification.

## Implemented in existing EmpireOS repository

- `empire_os/workspace_solar_reply_tracking.py`: one tiny **metadata-only**
  bounded Workspace reader with six exact verified recipient, sender, Gmail
  thread ID and sent-message ID anchors. Reuses the EXISTING Workspace
  provider's authenticated service and Gmail `threads.get(format=metadata)`.
  Six/6 matching real `SENT` anchors are required in **the right mailbox**
  before any batch scan counts as proven. Reply-looking messages are only
  `INBOUND_PROVIDER_HEADER_CANDIDATE_NEEDS_HUMAN_REVIEW`: they still need
  actual sender/body/provenance review before being called a buyer reply,
  opt-out, commercial intent or CRM opportunity. Each thread and Gmail message
  ID is deduplicated and rejects partial/incomplete results.
- `scripts/poll_workspace_solar_outreach_readonly.py`: optional explicit
  `--write` stores a strictly bounded 0600 **metadata-only** snapshot at the
  existing `runtime/buyer_network_intelligence/workspace_solar_outreach_reply_review_latest.json`
  using the existing atomic private writer. Default is observe/no write.
  It never touches `buyer_partner_message_index_20261010.json`, because
  that index belongs to the other authenticated personal mailbox. Never
  stores bodies, snippets, subject lines, personal correspondence or tokens.
  Does not send mail, change labels, alter EmpireDB, create contacts, resolve
  tenant authority, approve follow-ups, issue contracts or claim revenue.
- `tests/test_workspace_solar_reply_tracking.py`: bounded exact-identity,
  no-send, anti-forgery, dedupe, candidate, completeness and credential-gate
  checks. Synthetic test metadata is NOT customer reply evidence.

## Real send evidence from connected Gmail

| Business | Exact Gmail thread | Verified SENT message |
|---|---|---|
| GB NRG | `1a14f24fdcaa1d01` | `1a14f282abf361e4` |
| Perfect Sense Energy | `1a14f2505c538311` | `1a14f28336a3968c` |
| Solar4Good | `1a14f250aa228b3e` | `1a14f283948b5788` |
| Sustain Commercial Solar | `1a14f2fddadfeb8a` | `1a14f36a4bfdb0ec` |
| SOL PV Group | `1a14f2fe3468400e` | `1a14f36accbf3a56` |
| 100% Renewables | `1a14f2fe80133909` | `1a14f36b276ff3c2` |

All six messages have been independently read back from the authorised
connected Gmail account with `SENT` labels and intended recipients.
The latest 18 October Gmail search found no genuine new inbound from these
six domains and no bounce/delivery notice in the checked Workspace inbox.
Absence of a bounce does **not** prove delivery.

## Operator usage / gates

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.poll_workspace_solar_outreach_readonly
# Only AFTER Workspace Gmail readonly token is safely reauthorised:
./.venv/bin/python -B -m scripts.poll_workspace_solar_outreach_readonly --write
```

Today the non-writing command must **hold** with
`WORKSPACE_GMAIL_READ_SCOPE_NOT_CONFIGURED` and
`verified_sent_anchors_in_live_mailbox=0`, NOT falsely return a success
from the six stored IDs. The six provider-confirmed sends in this document
remain real historical evidence, separate from an authorised **live**
Workspace server scan.

Once the existing Workspace reader is explicitly authorised via the
original Google OAuth process, this same code needs no new list or send
service; verify real scan completeness and 0600 private file permissions.
A reply candidate then belongs to the **existing founder review/CRM identity
workflow**, not automatically to `revenue_crm_prospects`, since the latter
requires independent legitimate business-entity/tenant binding. Never create
prospect rows from an outbound SENT message or a bare metadata-only reply.

**Still open:** correct Workspace read-only authorisation and the exact
provider-backed prospective reply → reviewed founder CRM path.
No manufactured enquiries, new mail sends or production customer
mutations were used to demonstrate this release.

## Deduplication / history safety

The optional private snapshot also records `new_inbound_header_candidate_count`
after comparing against the previous complete, authenticated Workspace scan.
Repeated reply IDs are not re-counted. Incomplete/changed historical anchors,
unsafe prior file permissions, missing previously observed candidates or a
partial thread scan hold the update instead of resetting the baseline.
Counts are metadata candidates for a founder review, not verified replies.
**21 isolated deterministic tracker tests passed**, including snapshot-diff
and no-send behavior.
