# EmpireDB 049 v2 — Isolated private buyer-status reader
13 October 2026 — **STAGED ONLY / NO PRODUCTION DDL**

## Why v1 was held

The founder's read-only 049 preflight returned
`HELD_PRIVATE_READER_049_GATES`: the production login
`empiredb_migrator_login` can LOGIN, INHERIT and SET
`empiredb_migrator`. Consequently SECURITY DEFINER owned by the
migrator and an RLS policy TO migrator would extend the new buyer status
read path to a real, existing migration login. Never revoke or change
that legitimate production membership just to pass a new release gate.

The founder's parent-table RLS inventory then verified:
- `direct_bsc_buyer_capabilities`: owner migrator; ENABLE + FORCE RLS;
  0 policies, owner-only ACL after successful 047/048.
- `fulfilment_orders`: migrator-owned, ENABLE, not FORCE; 23 policies,
  11 permissive SELECT policies; no restrictive policies.
- `bsc_payment_requests`: migrator-owned, ENABLE, not FORCE; 10
  policies, 6 permissive SELECT policies; no restrictive policies.
- `bsc_payment_evidence`: migrator-owned, ENABLE, not FORCE; 9
  policies, 5 permissive SELECT policies; no restrictive policies.
- Existing default migrator grants: app SELECT/INSERT/UPDATE/DELETE,
  readonly SELECT. Do not alter global or schema default privileges.

These are metadata observations, not proof any payment occurred.

## What v2 proposes — revised 049, not a second production rollout

`migrations/empiredb/049_direct_bsc_buyer_status_private_reader.sql`
replaces the previously unapplied v1 source in the existing branch.
It executes atomically only after a *separate* founder approval:

1. Strictly recheck existing migrator login membership, source owners,
   forced RLS on capability, zero original policies/extra grants, and
   exact live parent policy totals of 23/10/9. Abort on drift.
2. Create **two purpose-specific NOLOGIN, NOINHERIT, NOBYPASSRLS,
   non-superuser roles** with no memberships:
   `empire_direct_checkout_status_owner` (restricted function definer)
   and `empire_direct_checkout_status_reader` (function caller).
3. Grant only specified SELECT **columns** across the four tables to
   the isolated owner. Grant no table SELECT to the caller.
4. Add exactly one new SELECT policy on each of four existing tables,
   targeted **only** at the isolated owner; the capability-table policy
   requires unrevoked, unexpired capability evidence. The three parent
   policies use `USING (true)` but can benefit only the isolated NOLOGIN
   owner with no members and are used by the bound SECURITY DEFINER
   function. This is a deliberate bounded expansion of internal read
   authority. Do not inaccurately call it zero-access or unaffected
   parent policies: existing policies remain intact, but new ones are
   added only for the isolated owner.
5. Create one `SECURITY DEFINER` function with fixed empty search_path,
   owned by the NEW isolated owner (never the migrator), that accepts
   only an HMAC fingerprint and checks exact order, buyer, request,
   terms SHA, payer, USDT cents, expiry and direct settlement.
   Its JSON output excludes customer email, idempotency key, bearer and
   transaction hash.
6. Revoke PUBLIC and existing app/readonly EXECUTE on that function;
   grant only EXECUTE to new NOLOGIN reader role, **without assigning
   any login**. Reject any unexpected default-function ACL grants.
7. Verify owner isolation, policy count/target, function ACL and app
   denial inside the same transaction. No public endpoint is created.

Production grants, migration ownership and login memberships remain
unchanged. There are no checkout service restarts, wallet operations,
billing authorisations, or outbound sends in migration 049.

## Independent verification evidence

- Python security and preflight/operator contract suite: **165 passed**
  across disjoint latest runs; one existing Starlette warning.
- Disposable PostgreSQL 18, port other than 5432: exact 047 and 048
  migration starting state, parent policy totals, and *existing* migrator
  login membership retained throughout. Extra unexpected migrator member
  fails 049 before creating roles, with transaction rollback.
- Exact 049 v2 SQL installed in disposable PG18, followed by
  **12 PASS** named independent catalog checks.
- HMAC fingerprint lookup succeeds only for matching order/request.
  Guessing, revocation, altered amount, wrong buyer and repeated 049
  application fail. Migrator LOGIN remains active but cannot see new
  capability rows or execute the new function. Reader has no direct
  table SELECT, only function EXECUTE.
- NO production 049 migration, role/policy grant, API, secret, customer
  payment or blockchain execution was performed.

## Future guarded production installation — NOT AUTHORISED

The separately guarded operator is:
`scripts/deploy_empiredb_direct_bsc_private_reader_049.sh`.

It requires exact founder approval for 049 **v2**, both proposed
NOLOGIN roles, their specific column SELECT privileges, four
role-specific RLS SELECT policies and the bounded SECURITY DEFINER
function. It checks canonical database/checkout flags, the committed
SQL and preflight hashes, the v2 read-only production preflight,
the verified existing 048 backup, and creates a fresh full root-only
database/global-role backup. It then performs 12 independent catalog
security readbacks and rechecks checkout payment flags. No full
restore rehearsal is claimed. If any failure occurs after COMMIT, it
stops without a blind retry.

Run **only the safe read-only v2 preflight now**:

```bash
cd /srv/empire_os
set +e
sudo -n -u postgres ./.venv/bin/python \
  -m scripts.inspect_direct_bsc_private_reader_049 --preflight
echo "PRIVATE_READER049_V2_PREFLIGHT_EXIT=$?"
```

A READY result does **not** authorise the guarded production operator.
Request separate founder approval then, after reviewing exact grant and
policy scope. The private reader will still have no login or public
endpoint; follow-on token issuer/login/API and live payment activation
require their own gates.

Other user-pasted work on 13 October:
- The read-only suppressions query showed zero matches/intents for two
  marketing emails, but no outbound send authority came from that query.
- Windows PowerShell eventually copied a Google OAuth client JSON to
  the secure Ubuntu workspace after an earlier Bash/PowerShell shell
  mix-up. That demonstrates file transfer only, not Google mailbox
  authentication or permission to send mail. Keep OAuth credentials
  private and outside Git history.
