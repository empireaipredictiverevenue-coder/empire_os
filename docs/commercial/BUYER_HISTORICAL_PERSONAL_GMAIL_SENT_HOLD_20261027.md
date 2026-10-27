# Buyer contact-history repair — 27 October 2026

## Scope

The original EmpireOS buyer acquisition programme sometimes sees older personal
Gmail outreach as `UNKNOWN_HISTORY` because the original importer intentionally
tracks a bounded number of canonical existing threads. That does **not** mean
the recipient is safe for an additional cold introduction.

This bounded fix adds an optional, read-only, **0600 private** original
historical Gmail SENT evidence source at:

`runtime/buyer_network_intelligence/personal_gmail_historical_sent_20261027.json`

Its schema is `empire.buyer_personal_gmail_historical_sent.v1`. Only exact
sender-mailbox, recipient-domain, sent-message ID, thread ID, RFC3339 UTC date
and SENT-label tuples independently reviewed through the connected personal
Gmail account can enter this particular snapshot. No mail body or OAuth token
is stored. Absence of a domain **never means it has not been emailed**.

## Concrete verified held identities

- Advertising Results (`advertisingresults.com`): personal Gmail
  `SENT`, 13 October 2026 09:52:49 UTC,
  `1a134add2f0e832f`, thread `1a134ab6ab1988d1`,
  exact recipient `email@advertisingresults.com`.
- Summit Leads (`summitleads.ai`): personal Gmail `SENT`,
  13 October 2026 08:59:48 UTC, `1a1347d4bf3f29c4`,
  thread `1a1347d4bf3f29c4`, exact recipient `team@summitleads.ai`.

Gmail confirms these messages were sent. This is **not** evidence of delivery,
buyer approval, an active campaign, an accepted call, capacity or paid revenue.
The original `buyer_network_contact_history_gate.review` returns
`PERSONAL_GMAIL_SENT_ALREADY_CONTACTED`, `outbound_authorized=false`.
Original opt-outs and delivery holds win on precedence. Untrusted metadata,
invalid provider labels, mismatched recipient domains, symlinks or incorrect
permissions cause the entire history gate to fail closed.

## Operating ownership

The original Workspace sender/receipts and the existing hourly commercial reply
watch continue unchanged. The separate manually curated historical input is not
a second mailbox poller, new database, outreach service or recurring agent.
It is not presented as complete historical coverage.

The founder approved continued buyer acquisition, not additional automatic
permission to send. A buyer still requires an authenticated reply containing a
live buy-box, written payable event and settlement terms before activation.

Test scope: `tests/test_buyer_personal_gmail_historical_hold_20261027.py`
plus the existing contact-history and Workspace source-guard tests.


## One independently reviewed cross-domain contact (27 October, 18:23 UTC)

The original first-party publisher page `https://namasteynetwork.com/home-services.html` explicitly lists `namastey@namasteymail.com`. The founder personal-Gmail thread `1a0d9de9548a5945` contains a verified SENT message `1a12771d14fd8d2e` to that exact published address on 10 October 2026. Although the contact mailbox is on `namasteymail.com`, the brand's public site domain is `namasteynetwork.com`. The existing contact-history reader consequently missed the archived sent receipt for the site identity after the original registry changed.

An exact single reviewed mail-domain alias is now applied **only if the actual privately stored `namasteymail.com` SENT proof passes validation**. It holds the `namasteynetwork.com` site identity against repeat first introductions, preserves opt-out precedence, and authorizes no outreach. No generic domain-alias discovery and no unreviewed equivalence are enabled. A missing or invalid original sent record still returns UNKNOWN/SOURCE_UNAVAILABLE rather than fabricating contact.
