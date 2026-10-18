# REV053 — first *existing* canonical revenue-event evidence read

**18 October 2026 | Founder-approved continuation | OBSERVE only | EmpireDB**

## Verified prerequisite

Production REV051 restricted reader/function and REV052 tenant-bound SCRAM
login were confirmed in the founder's live terminal. The final REV052 check
was `REV052_EXISTING_RESTRICTED_LOGIN_VERIFIED`, `failure_stage=NONE`,
`EXIT_CODE=0`. All 16 admin-only catalogue checks passed, as did actual
authenticated login, SET LOCAL ROLE, execute and zero-result sentinel proof.
See `EMPIRE_REV052_PRODUCTION_AUTHENTICATED_READER_PASS_20261018.md`.

This means the identity and function are ready. It does **not** mean one
genuine commercial revenue event has yet been found.

## Smallest useful read-only next step

New reviewed operator:
`scripts/review_rev053_one_live_revenue_event_readonly_20261018.py`.

It requires an explicit `--read-only-one-event` flag and root operator
on the known canonical server. It performs only:

1. One bounded DBA `BEGIN READ ONLY` inspection of the existing login,
   role, trusted exact tenant binding and all three source-table denied ACLs.
   Any drift is HOLD before opening a credential.
2. One bounded DBA `BEGIN READ ONLY` SQL query with a 5-second statement
   timeout, returning **at most one UUID internally** from existing
   `public.commercial_events`, bound to the same founder tenant through
   existing buyers and fulfilment order relations. Checks exact type
   `revenue_recognized`, actual_revenue flag, positive matching
   event/order price, matched product and buyer, order state settled or
   outcome_captured and non-null settled_at, matched nonempty lineage and
   no future event timestamps.
3. If no row matches, emit
   `REV053_NO_ELIGIBLE_EXISTING_EVENT_FOUND`. That is **not proof of zero
   revenue**, nor a reason to synthesize any production event.
4. If there is one candidate, open the existing root-owned 0600 credential
   from `/etc/empire/revenue-event-evidence` without printing it, and
   use `empire_os/predictive_revenue_canonical_reader.py` unchanged to
   invoke the single exact-event restricted function under the authenticated
   REV052 login and `SET LOCAL ROLE`. A session-only UTF8 client encoding
   normalises PostgreSQL SQL_ASCII test-cluster text results while retaining
   the first-party validator and preserving all DB privileges.
5. Only if the original first-party validator accepts the returned single
   event/order record, emit the status
   `REV053_ONE_EXISTING_CANONICAL_LEDGER_EVENT_MATCHED`, a SHA256-derived
   truncated non-reversible event reference fingerprint, the event occurrence
   time and positive `amount_minor_units`. It deliberately makes **no
   unsupported currency unit assumption**, no claim of bank settlement,
   refund/chargeback finality, signed customer contract, legitimate
   paid demand, daily total or realised revenue.

The script never prints customer names, addresses, source event UUID, order
UUID, lead data, full raw payloads, credentials or DSN. On unreadable
information, privilege failure, race, invalid bytes, missing provenance or
timeout, it fails closed with a status and stage only. Never grant new
permissions or change tenant bindings to make it pass.

No DDL, HBA, password creation/rotation, DB write, new schema, order, test
payment, live blockchain action, customer report, email, HTTP endpoint or
outbound automation is included. The main repository's untracked first-party
reader remains owned by the concurrent agent and was **not overwritten**.

## Full isolated PostgreSQL 18 test

`scripts/test_rev053_one_event_ephemeral_20261018.sh` reuses the existing
disposable REV052 fixture, with synthetic multiple tenants, orders and
revenue events. It verifies:

- Restricted SCRAM login and tenant/role proof.
- Direct ledger-table SELECT denied, cross-tenant reads denied, wrong
  password rejected.
- The optional hardened schema with no public USAGE: the restricted
  login still accesses only the approved SECURITY DEFINER event function.
- A single synthetic already-existing qualifying record is discovered by
  the actual reviewed admin SQL, then fetched via the **original** first-party
  reader's exact event UUID/tenant parameters.
- Synthetic event price/lineage and positive amount are validated; test
  status is `REV053_ONE_EXISTING_CANONICAL_LEDGER_EVENT_MATCHED`.
- A generated test fixture is **not** represented as real production revenue.

Source/unit tests exercise no candidate, failed ACL, malformed event UUID,
fake attestation, secret redaction and the distinction between one ledger
event and verified external payment/realised revenue.

## Only after reviewed commit: one founder-local read-only run

```bash
cd /srv/empire_os
sudo timeout --signal=INT --kill-after=5s 55s \
  ./.venv/bin/python -B -m scripts.review_rev053_one_live_revenue_event_readonly_20261018 --read-only-one-event
echo "EXIT_CODE=$?"
```

`EXIT_CODE=0` only if one existing source event independently passes
the first-party verifier; `EXIT_CODE=2` is an honest HOLD/absence state;
`EXIT_CODE=124` is a bounded timeout. The terminal result may show
minor units but **not a currency assumption or proof of money received**.

Remaining real revenue gap after a positive match: verify an independent
payer, contract, payment transaction/receipt and external settlement,
fulfilment, refunds, realized profit, and independently complete daily
revenue census. Only such evidence justifies further commercial claims.
