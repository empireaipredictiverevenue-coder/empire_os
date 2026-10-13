# Empire AI — Buyer-bound BSC payment status, private reader 049
13 October 2026 · **HELD / CODE PREPARED / NEVER APPLIED**

## Canonical production starting point

- Approved migration 047 committed on 13 October; founder observed actual
  postcommit app SELECT permissions from migrator default grants.
- Separately approved 048 repaired **only the 047 capability table's** named
  ACLs. User terminal verified 048 exit 0, all nine postcommit checks PASS,
  forced RLS ON, both the ordinary app and readonly role denied, checkout
  proposal and order flags OFF.
- The table remains deliberately SEALED, with no RLS policies. There is
  currently no private buyer status role, provider credential, public
  endpoint or customer token delivery integration.
- No off-chain read or database status is proof of an actual BSC transfer.
  Independent human approval and on-chain verification remain gates.

## Completed implementation (offline only)

1. `empire_os/direct_bsc_buyer_status_private_reader.py` implements the
   minimal HMAC token -> fingerprint -> authenticated DB read -> independent
   response-projector chain. SQL receives only the fingerprint, not bearer.
   A generic denial hides all backend errors and internal role credentials.
   Its dedicated transport starts `SET TRANSACTION READ ONLY`, assumes
   only `empire_direct_checkout_status_reader`, and accepts no arbitrary SQL.
   It refuses to reuse the configured general app DSN.
2. `migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql`
   is an **unapplied proposal** for a NOLOGIN/NOINHERIT permission role,
   a SELECT-only policy for the existing NOLOGIN `empiredb_migrator`,
   and a tightly bound SECURITY DEFINER function. The function requires
   the exact fingerprint, order ID, buyer ID, request ID, USDT amount,
   accepted price, immutable terms and payer wallet to match, and only
   returns a minimal internal JSON projection. No customer email, payment
   transaction hash, idempotency key, business contact or raw token.
3. That function's EXECUTE authority is only the new NOLOGIN reader role,
   with **no membership assigned to any login**. Application roles have
   neither EXECUTE on the new function nor SELECT on the sealed
   buyer-capability table; existing parent-table privileges are unchanged.
4. The new RLS policy is scoped to the NOLOGIN migrator owner *only*, to
   support the SQL SECURITY DEFINER lookup. Importantly 049 refuses to
   create a policy if *any* role can assume/inherit the migrator, or if
   047/048's table is not owner-only ACL sealed. The new reader role must
   have NO direct memberships. The migration is atomic; a second attempt
   fails closed and is never an activation mechanism.
5. `scripts/inspect_direct_bsc_private_reader_049.py --preflight` is a
   strict, read-only PostgreSQL catalog and permission inspector for these
   exact prerequisites. It does not inspect any customer or wallet rows.

## Test evidence, source only

- Python buyer security, private transport and 048 regression subset:
  **111 passed**. One-time bearer fingerprint binding; expiry, revocation,
  price, payer, customer, order, request and human approval checked.
- Disposable PostgreSQL 18 installation: **PASS**. Independently applies
  exact 047+048 fixture, attempts 049 with reverse migrator membership
  (rejects atomically), removes only the test membership and applies 049.
- Private function reads the correct digest but not an unknown digest.
  Its role has no SELECT on capability, order or request tables and app
  cannot EXECUTE the function. Mutating payable amount or buyer ID hides
  the record; revocation immediately denies a formerly valid token.
  A second 049 install attempt is blocked.
- All test DB mutations occurred on disposable PG18, **not** EmpireDB.
- No production SQL, role GRANT, RLS policy, service restart, login
  credential, public endpoint, wallet send or money collection performed.

## Remaining hard gates (not implicitly approved)

**Separate founder approval required** to install *just* private-reader
migration 049, if and only if the canonical preflight proves production
parent-table SELECT for the migrator, exact forced RLS/zero existing
policies, owner-only table ACL, dedicated role/function absence and **zero
incoming memberships of the migrator**.

Run only the read-only preflight at this point:

```bash
cd /srv/empire_os
set +e
sudo -n -u postgres ./.venv/bin/python \
  -m scripts.inspect_direct_bsc_private_reader_049 --preflight
echo "PRIVATE_READER049_PREFLIGHT_EXIT=$?"
```

Even a ready result is NOT deployment approval. Next separate engineering
steps: private issuer with distinct trusted login/role and atomic capability
binding after approved request proposal (047 request_id NOT NULL), safe
one-time delivery and recovery via sovereign founder mailbox, named
independent reader login authentication verification, and first-party
same-origin POST status endpoint with noncacheable/rate-limited responses.
The public gateway previously committed order-ingress changes also require
separately approved controlled deployment.

**Do not tell buyers to send USDT before independent human approval.**
Checkout proposal, order activation, blockchain transfer and revenue
recognition remain OFF.


## 13 October 2026 — live preflight v1 HELD: existing incoming migrator membership

The founder executed the unmodified canonical read-only 049 preflight and
returned:

- canonical_empiredb, source tables, migrator source SELECTs,
  forced-RLS owner-only sealed capability table: **PASS**
- dedicated reader role and function absent: **PASS**
- `migrator_has_zero_incoming_memberships`: **FALSE**
- status: `HELD_PRIVATE_READER_049_GATES`; exit code 2
- migration 049 **NOT APPLIED**, no reader login, no endpoint, money OFF.

This is different from the **outgoing** `empiredb_migrator →
empiredb_tenant_reader` membership previously inspected for 047.
An **incoming** membership means another role is a member *of*
`empiredb_migrator`. No role name or SET/INHERIT authority was returned in
the original 049 preflight, so a security interpretation or role alteration
would be guesswork.

The original fail-closed condition is deliberately preserved. The source
inspector was enhanced to return `migrator_incoming_member_details`
(granted member role name, LOGIN/SUPERUSER, inherited, SET, ADMIN flags)
and `non_superuser_logins_with_migrator_membership` (transitive MEMBER
paths only), all from the PostgreSQL system catalog in a READ ONLY
transaction. It never reads contact, customer, payment, token or secret
rows. Its result is not an authorisation to alter any membership or apply
migration 049.

Next exact user-side, read-only check:

```bash
cd /srv/empire_os
set +e
sudo -n -u postgres ./.venv/bin/python \
  -m scripts.inspect_direct_bsc_private_reader_049 --preflight
echo "PRIVATE_READER049_PREFLIGHT_EXIT=$?"
```

The new result remains HELD until the actual role lineage is reconciled.
If a legitimate production login can SET/INHERIT the migrator, prefer a
**distinct purpose-owned NOLOGIN security definer with no memberships**
and separately approved, narrowly audited ACL/RLS policy rather than
removing the other system's role privileges or weakening this gate.
This is a possible future design, not an approved or installed change.
