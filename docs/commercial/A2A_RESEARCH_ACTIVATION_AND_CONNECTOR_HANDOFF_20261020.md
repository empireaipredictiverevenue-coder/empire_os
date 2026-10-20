# EmpireOS A2A Commercial Research — Activation and Provider Handoff

20 October 2026. Worktree: /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020
Branch: feature/a2a-commercial-signal-mining-20261020

## Activated Phase 1: isolated hourly research tick

The installed user-level systemd files are:
- ~/.config/systemd/user/empire-a2a-commercial-intelligence-research.service
- ~/.config/systemd/user/empire-a2a-commercial-intelligence-research.timer

Source files are versioned in ops/systemd/user in this branch.
Ubuntu loginctl reports Linger=yes. User-level timer schedules OnCalendar=hourly
with up to 120 seconds randomized delay and Persistent=true.

Service executes ONLY:
PYTHONPATH=<isolated_worktree> /srv/empire_os/.venv/bin/python -B \
 -m scripts.run_a2a_commercial_intelligence_cycle_v2_20261020 --write-local

Reports go only to <isolated_worktree>/runtime/a2a_commercial_signal_mining.
No source modifications, crawler, CRM writes, Meta requests, contact actions,
outbound, posting, payment or database writes from this implementation.

Service protections: ordinary ubuntu account, filesystem read-only except the
worktree's report directory, UMask=0077, NoNewPrivileges, PrivateTmp,
RestrictAddressFamilies=AF_UNIX, TimeoutStartSec=120, MemoryMax=256M,
CPUQuota=25%. This worker contains no network operations. Full host egress
blocking was NOT independently verified: user-level systemd IPAddressDeny was
removed after systemd warned IP firewalling could not enforce it without root.

Verify:
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user status empire-a2a-commercial-intelligence-research.timer
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user show empire-a2a-commercial-intelligence-research.service \
 -p Result -p ExecMainStatus -p RestrictAddressFamilies -p ReadWritePaths
journalctl --user -u empire-a2a-commercial-intelligence-research.service -n 25

Rollback ONLY THIS NEW TIMER (does not touch other agents):
XDG_RUNTIME_DIR=/run/user/1000 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus \
 systemctl --user disable --now empire-a2a-commercial-intelligence-research.timer

Do not delete the worktree while this timer remains enabled.

## Phase 2: local cryptographic identity provisioned, external trust not activated

Local-only Ed25519 identity created by:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.provision_a2a_commercial_miner_identity_20261020 --provision-local
Single-use provision refuses existing identity. Secret key file mode 0600 in an
ubuntu-only 0700 directory OUTSIDE the repository:
~/.local/share/empire_ai_a2a_signal_miner_identity

Verify using --verify-local. Local tests verify a signed discovery claim, reject
reused nonces in a test-local in-memory registry, and reject an unknown peer key.
Do not print or copy the private key, send it to ChatGPT, commit it or place it
in any environment variable containing other production service permissions.

CRITICAL: Production public gateway A2A authentication is still NOT ACTIVATED.
The existing runtime reports missing:
EMPIRE_A2A_TRUSTED_ED25519_KEYS_JSON,
EMPIRE_A2A_IDENTITY_DSN,
EMPIRE_A2A_INTENT_DSN.
The existing trusted A2A owner must review key management, persistent nonce
store, Postgres connection entitlements, A2A permissions, replay and gateway
restart/rollout separately. The agent has a candidate discovery card but is not
a trusted public/third-party commercial A2A agent.

## Phase 3: Meta business connection blockers

New read-only preflight:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
 -m scripts.review_a2a_external_connection_readiness_20261020 --write-local

Preflight marks (proposed names, not established existing server settings):
META_APP_ID; META_APP_SECRET; META_PAGE_ID;
META_IG_BUSINESS_ACCOUNT_ID; META_PAGE_ACCESS_TOKEN.

All are currently absent from the checked EmpireOS runtime environment. Owner
must specify the exact Facebook Page and associated Instagram professional
account, complete Meta app OAuth, scopes review, any app review, account
access proof, token lifecycle and webhook security. Product scopes vary by Meta
API version, account model and permission; use current official documentation.
Instagram business conversation automation is only via permitted channels and
app requirements. No prohibited Facebook Group scraping or unsolicited bulk DMs.

Config presence is not verification, and publication / inbox reply are distinct
capabilities with separate founder-approved release gates.

The optional Windsor.ai ChatGPT connector can simplify viewing connected
account analytics but connection inside ChatGPT does NOT add credentials to
this in-house EmpireOS server.

## Phase 4: Stripe finance connector blockers

Proposed non-secret status keys: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET.
Both are absent from the checked environment. Do not share keys in chat.
Connect a Stripe business account through an approved provider OAuth/API setup,
use sandbox keys and independently verify a checkout link lifecycle and webhook
signatures before any real money moves. Finance OS owner must own payments,
refunds, fee reconciliation and invoice fulfilment records, not the research miner.

Two distinct use cases:
(A) customer payment link -> provider-hosted checkout -> signed webhook ->
    canonical Finance OS reconciliation;
(B) agent purchasing with a restricted virtual card or wallet, requiring a
    supported issuer, separate financial approval and customer eligibility.

Stripe ChatGPT connector is an optional assisted access route; it does not
provision EmpireOS automatically or authorise agent payments.

## Production deployment status

Only the isolated research timer is activated. The existing production checkout
is busy with many unrelated changes, so no main checkout merge, production
gateway restart, A2A external trust activation, Meta connection or payment
service change was made. The service calls the isolated worktree explicitly.

Before broader rollout: existing source/identity/Buyer Scout/Data Brokerage/
Campaigns/Finance OS owners review their typed interfaces and secure delivery
requirements. Standard production release then merges the branch and moves
the timer to a maintained production code path, with regression and rollback.
