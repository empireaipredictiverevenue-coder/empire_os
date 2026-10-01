# Revenue Activation Runbook — 2026-10-01

Status: CANDIDATE / PREPARED / NOT ACTIVATED

## Objective

Activate zero-paid-media owned/organic acquisition and governed A2A commercial
intent without bypassing founder gates or inventing commercial evidence.

## Current truth

- closure drop fd7b9248 is promoted;
- five owned campaigns are prepared;
- paid-media spend is zero;
- canonical_intake_schema is the only owned-campaign blocker;
- migration 025 remains founder-gated and unapplied;
- A2A public discovery is live;
- A2A authenticated commerce remains fail-closed until trusted Ed25519 keys,
  identity DSN and intent DSN are supplied;
- public gateway requires the prepared systemd drop-in to load /etc/empire_a2a.env;
- service restart remains founder-gated;
- Seth and Kieran sends remain founder-gated and explicitly request owned/organic routes only.

## Activation order after approvals

1. Apply migration 025 using the migrator role in one transaction.
2. Verify tables, functions, grants and dedicated empire_owned_campaign_ingest role.
3. Configure the least-privilege campaign intake runtime DSN/role.
4. Install the public-gateway A2A EnvironmentFile drop-in.
5. Configure /etc/empire_a2a.env with trusted external-agent public keys and
   dedicated A2A identity/intent DSNs.
6. Restart public gateway once.
7. Verify A2A discovery/commerce routes and campaign intake fail-closed/live checks.
8. Publish the five zero-paid-spend owned research routes.
9. Observe first-party page/CTA/enquiry evidence.
10. Only then advance genuine demand into Sell Now; no inferred economics.

## Rollback

- disable/uninstall the A2A drop-in and restart the public gateway;
- stop publication of owned research routes;
- do not delete captured canonical evidence;
- migration rollback must be treated as a separate destructive DB decision,
  not an automatic action.

## Explicitly not authorized by this runbook

Paid traffic, automatic outbound, binding terms, allocation, payment/funds,
revenue recognition, migration 018 changes, or destructive repository cleanup.
