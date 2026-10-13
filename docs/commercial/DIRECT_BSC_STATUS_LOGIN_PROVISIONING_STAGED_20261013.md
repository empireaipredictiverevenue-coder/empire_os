# Direct BSC buyer status — dedicated issuer/reader logins (staged)
13 October 2026 · **SOURCE ONLY; NO CREDENTIALS OR PRODUCTION ROLE WRITES**

## Production truth
- Founder-executed migration 049 v2: COMMITTED, 12/12 postcommit controls PASS.
- Founder-executed migration 050 v1: COMMITTED, 10/10 postcommit controls PASS.
- Checkout health: online; payment proposal, binding orders, payment execution
  and revenue recognition all OFF. Chain configured, independently unverified.
- Two 049/050 restricted NOLOGIN roles exist; no dedicated LOGIN yet.
- Buyer status HTTP component staged, but not included in public gateway.

## What is built, not applied
`scripts/provision_direct_bsc_buyer_status_logins.py` provisions ONLY
`empire_direct_checkout_status_reader_login` and
`empire_direct_checkout_status_issuer_login` with freshly generated
**different** secrets. Each login is LOGIN NOINHERIT NOBYPASSRLS,
non-superuser, has exactly one corresponding NOLOGIN membership with
INHERIT FALSE and SET TRUE. No table grants, checkout activation or
public endpoints. Existing roles and grants are preserved.

Before any role write, operator verifies exact 049/050 independent
catalog proofs, the checkout OFF state, canonical local EmpireDB on
port 5432 and absence of an existing env file. Refuses remote
`hostaddr` override or noncanonical port. Secrets supplied only on
psql stdin; never printed or placed in command arguments. After role
creation, distinct database authentication tests inspect the actual
`session_user`, explicit SET ROLE, capability SELECT/INSERT denial,
cross-role execute denial and own-function permission. Only after
verification does it write the two DSNs to
`/etc/empire_direct_bsc_buyer_status.env` (0600). An ambiguous
partial failure must be investigated by catalog readback; **do not
repeat**. No live token is issued by provisioning.

**No account/credential production deployment is approved yet.** The
standalone command without flags prints STAGED and makes no changes.
The separate explicit installer token is
`--apply --approved-isolated-bsc-status-logins-only`, which must NOT be
used until separate founder permission for exactly the two limited
login identities, generated secrets and protected env file.

## Independent validation
- Python tests in
  `tests/test_provision_direct_bsc_buyer_status_logins.py` cover
  default OFF, exact approval, canonical DSN, distinct password-role
  matching, env overwrite refusal, installed-role readback and
  byte/string-normalised role identity without weakening permissions.
- The isolated PostgreSQL 18 harness
  `scripts/test_direct_bsc_buyer_status_logins_ephemeral.sh`
  recreates migrations 047–050 in temporary cluster, uses disposable
  passwords, verifies two LOGIN connections, role switching, absence of
  broad rights and denial of cross-role or second provisioning. Port
  5432 is never touched.
- A genuine bug was found and fixed **before activation**: the
  initial provisioner reused the issuer password for both roles.
  The SQL now indexes `passwords[login]`, with explicit regression.
- Disposable PostgreSQL in SQL_ASCII can return role names as bytes.
  ASCII decoding for exact role comparisons was added; no role or
  privilege requirement was relaxed.

## Remaining checkout integration
1. Separate founder approval to create exactly two PostgreSQL LOGINs
   and write their root-only DSNs.
2. Secure first-party key custody, buyer identity binding, one-time
   status token delivery and revocation workflow; no unsolicited sends.
3. Authenticated, abuse-controlled release of already-tested status
   handler behind HTTPS with tokens only in POST body.
4. Independent BSC chain/USDT/treasury/confirmations and paid
   fulfilment proofs before collection or realised revenue claims.

No payment execution, mail systems, orders or public services were
activated here.

## Observed authorised pending-order release

On 13 October at 19:49:52 UTC, checkout restarted with the
root-owned, non-world-writable active systemd override
`40-direct-bsc-controlled-release.conf`, containing the comment
`Founder-approved four-product direct BSC order admission`.
Checkout now reports `payment_proposal_authorized=true` and
`binding_order_creation_authorized=true`, while `payment_execution=false`,
`revenue_recognition=false` and BSC chain unverified. This is pending
order admission, not observed revenue or settlement.

The provisioning admission check now accepts this *specific* already
authorised release, only after verifying the root-owned file, exact
switch lines and active systemd DropInPaths. It also accepts both
proposal/order flags OFF. It rejects mismatched flags, missing release
proof or any payment_execution/revenue_recognition activation.
No runtime flags were changed by this source patch.

## Approved dedicated-login rollout — 049+050 compatibility correction

On 13 October the founder expressly authorised *exactly two restricted
PostgreSQL LOGIN identities and a protected local DSN file*, without
customer-facing routes, payment execution or revenue recognition.

The historical 049-only postcommit verifier assumes its original
one capability RLS policy and 11 payment-request policies; migration
050 intentionally introduced a second capability policy and a 12th
request policy. Therefore the original 049 verifier MUST NOT be run
unmodified as a gate after 050.

New `scripts/inspect_direct_bsc_reader_049_after_050.sql` preserves the
12 original independent security predicates while expecting the
documented post-050 policy totals (2 and 12). The distinct 050
postcommit proof still checks 10 separate controls, including its exact
policy and issuer function identities.

The provisioner now runs the two version-correct read-only proofs
before any LOGIN creation, pins privileged psql to
`/var/run/postgresql`, port `5432`, and refuses stale or ambiguous
role/credential state. Disposable PostgreSQL 18 independently verified
12/12 and 10/10 readbacks followed by both dedicated LOGIN
authentications, strict role isolation and second-apply denial.

Do not repeat a role provisioning command following any ambiguous
post-commit error. Check catalog roles, membership and presence of the
root-only env file first. No public endpoint or payments are activated
by this separately authorised work.
