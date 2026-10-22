# Founder authenticated Kanban read — existing CRM session canary

22 October 2026. The backend already runs the pinned two-file CRM release
at `/opt/empire-ai/crm-pilot-releases/agent-kanban-crm-20261022v1`.

## Independent runtime proof already seen

- Existing `empire-revenue-crm-pilot.service` is active on loopback port 8783.
- `GET /health` → 200 and `GET /v1/revenue-crm/health` → 200.
- `GET /v1/revenue-crm/department-kanban` **without a token** → 401.
- `GET /v1/revenue-crm/department-kanban?tenant_id=invalid` without a
  token → 401. `GET /openapi.json` remains 404.
- The loaded CRM API hash matches the approved candidate
  `34ecda4b2c2b86540daa9c4d74c420b8d67add94267308d721d2e405c6b21a15`.
  Any offline note about release deployment must distinguish source code
  from this actual live server proof.

## Human-operated existing founder tenant canary

`scripts/verify_founder_crm_agent_kanban.py` reuses the *already provisioned*
first-party CRM login from `scripts/redeem_founder_crm_invitation_local.py`.
It neither provisions new users nor reads the signing key. The human founder
must use an **interactive SSH terminal** under `ubuntu`:

```bash
cd /srv/empire_os
PYTHONPATH=/srv/empire_os /srv/empire_os/.venv/bin/python -B \
  scripts/verify_founder_crm_agent_kanban.py --interactive-founder-read-only
```

The script prompts **once** with `getpass` for the existing founder CRM
password (never paste a password/token into chat). It obtains a short-lived
signed CRM token from the existing loopback first-party login, makes
only bounded GET requests to the tenant-safe Kanban endpoint, then discards
the in-memory token. It prints ONLY safe HTTP statuses and aggregate
counts, not a token, password, tenant UUID, IDs, evidence or contact data.

It proves:
1. Anonymous and spoofed-tenant anonymous reads return HTTP 401.
2. The existing founder login succeeds and the authenticated Kanban
   returns HTTP 200.
3. A forged `X-Tenant-ID` and query tenant claim using the SAME real signed
   session cannot change the returned canonical board snapshot.
4. Board metadata remains read-only, exact tenant scoped and bounded.

This is *one* authenticated founder tenant. If the tenant has zero eligible
work cards, success proves the access path but **does not independently prove
row isolation between multiple populated tenants**. A second separately
authorised tenant canary or properly isolated synthetic contract test is
still necessary for that stronger claim.

## Agent runtime gates remain

- No agent dedicated signing credentials have been distributed.
- No model agent or long-lived worker can claim tasks by self-asserting its
  SOUL/personality. Process evidence and trust broker key registration
  require distinct checks.
- No agent-to-agent messaging has been activated by this CRM reader.
- The canonical queue still owns leases, task state, independent review and
  governance. No external sends, payments or public A2A endpoint.

Do not run the interactive script from a web request, background job,
automated testing or untrusted shell. No password shall enter CLI flags,
repo files, logs or chat.
