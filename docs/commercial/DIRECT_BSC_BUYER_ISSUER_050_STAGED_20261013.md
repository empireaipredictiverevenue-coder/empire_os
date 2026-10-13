# Empire AI — direct BSC private token issuance and status HTTP integration
13 October 2026 · source-only branch release, **no production 050 deployment**

## Production position

- Canonical 047/048 committed and sealed.
- Founder's exact production 049 v2 operator output reported COMMITTED,
  backup verified at
  `/var/backups/empiredb/direct-bsc-private-reader-049/20261013T191124Z`,
  all **12/12 security controls PASS**, checkout flags still OFF.
- Private status function and 2 NOLOGIN roles installed after 049.
  **Neither is yet assigned to a dedicated login.**
- No live buyer-token issuance, customer-status URL, payment instruction
  dispatch, payment acceptance or revenue evidence is activated.
- Existing repo has unrelated edits by other workers. Stage ONLY the
  named new 050 issuer/source/test/docs files.

## New tested source

- `empire_os/direct_bsc_buyer_status_private_issuer.py` issues random
  256-bit opaque bearers, computes an HMAC fingerprint, and requires a
  committed database insert with exact returned fingerprint before
  returning a bearer. It refuses approved/expired/cross-order requests
  and broad application credentials. No mail send or outbound action.
- `migrations/empiredb/050_direct_bsc_buyer_status_private_issuer.sql`
  is **unapplied**. It preserves all prior roles and privileges,
  creates separate NOLOGIN issuer owner/caller roles, adds exactly
  two new SELECT/INSERT scoped RLS policies, grants needed individual
  columns to the owner, and installs a security-definer issuance
  function. The one-use issuer role is not assigned to any login.
  No payment approval, wallet movement, webhook or service activation.
- `empire_os/direct_bsc_buyer_status_http.py` defines a dependency
  injected POST-only status route, **not included in the running
  public gateway or internal checkout app**. It requires an explicit
  activation gate, exact origin, same-origin Fetch Metadata, bounded
  JSON token body, peer-based abuse control, no-cache/no-referrer
  headers and generic rejection without leaking order/DB details.
- `scripts/inspect_direct_bsc_private_issuer_050.py` performs the
  exact READ ONLY EmpireDB policy/role/function preflight.
- `scripts/deploy_empiredb_direct_bsc_private_issuer_050.sh` is a
  **staged and separately approval-gated** root operator, checked
  against committed SQL/preflight/postcheck sources; verifies
  checkout OFF, owner isolation, canonical database identity, verified
  049 backup, then takes fresh root-only full DB/global-role backup
  and applies SQL atomically. Independently checks 10 named
  postcommit conditions and rechecks checkout OFF. Stops on
  uncertain postcommit conditions — NO BLIND RETRY.
- `scripts/test_direct_bsc_private_issuer_050_ephemeral.sh` uses
  disposable PG18, exact 047/048+049 fixtures, issues through the
  isolated role, reads through the already installed role, and proves
  duplicates, cross-order, approved request issuance and app/migrator
  access fail closed. Test PG port != 5432, no production writes.
- Independent `scripts/inspect_direct_bsc_private_issuer_050_postcommit.sql`
  checks ten catalog security invariants using READ ONLY transaction.

## Evidence

- **182 Python tests PASS** including upstream 049 contract/reader,
  status HTTP, token issuance, release operator and preflight.
- **Disposable PG18 050 issuer migration and 10/10 postcommit checks
  PASS.** Issues only on a pending request, exact order/request bound;
  read succeeds, duplicate/wrong-order/postapproval issuance denied;
  second installation refused.
- Existing Starlette test client reports one deprecation warning.
- No prod 050 migrations, passwords, role login assignments, endpoint
  inclusion/restarts, mail sends, USDT transfers or revenue recognition.

## Next operations, in order

1. Founder/operator run read-only `scripts.inspect_direct_bsc_private_issuer_050`
   and supply output. READY is NOT permission to install.
2. After explicit **founder approval 050 only**, run the prepared 050
   installer exactly once; independently verify 10 postcommit checks.
3. Separate role provisioning gates for dedicated issuer/reader logins
   and secure credential placement, then authenticated integration
   into public gateway. Never reuse app DSN or founder mailbox secrets.
4. Implement and verify authenticated buyer identity binding, one-time
   token delivery via first-party founder mailbox, issue/expiry/
   revocation, persistent distributed rate limiting, redacted logs,
   same-origin HTTPS and safely disabled endpoints until release approval.
5. Independently confirm BSC RPC / chain ID 56 / token contract,
   treasury proof, approval gating, exact payment and 12 on-chain
   confirmations, product fulfilment and revenue evidence. Live payment
   and outbound switches remain founder-gated and OFF now.

## Read-only production preflight only

```bash
cd /srv/empire_os
set +e
sudo -n -u postgres ./.venv/bin/python \
 -m scripts.inspect_direct_bsc_private_issuer_050 --preflight
echo "PRIVATE_ISSUER050_PREFLIGHT_EXIT=$?"
```

Do not run the production installer without a separate approval for
exactly issuer 050 and its NOLOGIN roles, owner column grants, two
role-scoped RLS policies, and one security-definer function.
