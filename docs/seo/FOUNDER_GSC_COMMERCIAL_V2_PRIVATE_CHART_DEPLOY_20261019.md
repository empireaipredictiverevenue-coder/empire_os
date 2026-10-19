# Empire AI — founder-approved GSC charts deployment

19 October 2026 | Private console | Commercial Operations v2 baseline

## Owner approval and scope
Founder explicitly approved activation of the staged GSC impression
bars, click graph and exact daily source table in the existing private
Founder Console. This is a continuation of the existing Next.js
app, NOT a public site release, new service, DB migration, login
replacement, financial activation, or marketing send.

The active service is empire-founder-console.service, loopback
127.0.0.1:3001. Its current frozen worktree is
/opt/empire-ai/founder-console-releases/commercial-ops-v2-49aba1fa.
The staged candidate (built directly from that active release) is
/home/ubuntu/empire_worktrees/empire_founder_gsc_trends_commercial_v2_candidate_20261019.

## Preflight and activation

Before any service change:

    cd /srv/empire_os
    bash scripts/deploy_private_founder_gsc_trend_commercial_v2_20261019.sh --preflight

Expected: FOUNDER_GSC_CHART_PREFLIGHT_PASS, plus
FOUNDER_GSC_CHART_STAGED_NOT_DEPLOYED.

Founder-approved root operator (only if preflight still passes):

    sudo bash scripts/deploy_private_founder_gsc_trend_commercial_v2_20261019.sh --apply-founder-approved-private-gsc-trend-commercial-v2

The only systemd mutation is creating the new override:
  /etc/systemd/system/empire-founder-console.service.d/98-private-gsc-trend-release.conf

This changes ONLY WorkingDirectory to the pinned candidate. Previous
commercial-ops v2 97 and all earlier overrides remain. The existing
EMPIRE_SEARCH_API_BASE_URL continues to come from the earlier private
SEO release configuration. The script restarts the existing
empire-founder-console.service exactly once on success. It does not
restart Search Intelligence or expose the private page publicly.

## Release check conditions

- Exact source hashes, compiled Next.js artifacts and build ID
- Active Commercial Operations v2 identity and all six exact overlays
- Ten currently served private routes HTTP 200
- Existing SEO API responding with observed, first-party daily-series
  data and no ranking or revenue attestation
- Public /department and /v1/search/department/review both HTTP 404
- Private URL still binds only 127.0.0.1:3001
- Post-release live server-rendered GSC bars and clicks line
- Post-release all ten private routes still HTTP 200
- Existing private Search Intelligence service remains healthy

If any post-switch check fails, the EXIT trap removes ONLY the new 98
override and attempts to restart the original Commercial Operations
v2 service. The previous frozen release is never modified.

Manual rollback from an authorised Ubuntu shell:

    sudo rm -f /etc/systemd/system/empire-founder-console.service.d/98-private-gsc-trend-release.conf
    sudo systemctl daemon-reload
    sudo systemctl restart empire-founder-console.service

This script is not a verified founder identity gate: it preserves
loopback-only exposure and the public 404 boundary, but application-
level owner authentication still needs an independent review. No
SERP ranking, external AI citation, organic buyer or revenue claim
comes from the GSC chart. Date-dimension and page-dimension GSC
impressions are different report slices and are never added.
