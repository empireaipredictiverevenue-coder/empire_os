# Empire AI — PR / Editorial / Consultancy / Proposals integrated review (25 October 2026)

## Original systems and conservation rules

This bridge is an **on-demand, isolated REVIEW_ONLY stage**. No second CRM, database, publisher, scheduler, model, bot, or acquisition department. Its review packet draws from:

- The original PR/consultancy worktree on `agent/pr-consultancy-review-20261011`: exact Gmail sent receipts (two historical sends), publisher contact research, founder-approved three-price policy and the existing held contracts/intake evidence.
- The canonical Marketing & Growth `GROWTH_001` editorial pitches and AI-readiness original draft: independent editorial decisions and retained rights checks.
- The existing native buyer proposal handoff and existing tender consultant's founder handoff: internal review, not binding bids or sales.
- The existing Revenue Distribution snapshot in `runtime/revenue_distribution/latest.json` when passed as `--distribution-root`: **commercial traffic-supply inventory, not proof of independent PR placements**.

The snapshot has separate `pr`, `editorial`, `consultancy` and `proposal` lanes; stable review item IDs, hashes for all read evidence, and empty canonical CRM binding fields. Historical Gmail threads are linked by the **existing message-provider thread ID**, not fictitious CRM identities. The two recorded prior PR sends take precedence over older contact research saying `pitch_sent=false`; prevent duplicate pitching. New editorial submissions, journalist responses, qualified buyers, proposal acceptances, delivered contracts, payments and earned backlinks are **never inferred**.

## Current runnable stage

```bash
cd /home/ubuntu/empire_worktrees/earned_media_advisory_bridge_20261025
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_earned_media_advisory_bridge_20261025 \
  --review-only \
  --repo-root "$PWD" \
  --pr-root /home/ubuntu/empire_agents/empire_pr_consultancy_20261011 \
  --distribution-root /srv/empire_os
```

No write flags. The packet goes to stdout only, so it is not exposed on a public website or stored in a second ledger. Tests: `PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -m pytest -q tests/test_earned_media_advisory_bridge_20261025.py`.

## Proposed future connections — not falsely marked live

1. Existing Founder Console review desk consumes this reviewed packet through the original authenticated departmental read route (requires maintainer approval and tenant/auth verification).
2. Existing canonical Smart CRM links a record **only after** an exact company/person/tenant identity, verified existing thread, consent/suppression and legitimate source mapping are proven; link existing IDs, no broad CRM ingest.
3. Existing Marketing & Growth owner handles editorial rights/factual acceptance and ASTRA publisher. Journalist/PR pitches stay independent of consultancy CTAs and cannot demand backlinks.
4. Existing customer sales owner uses the approved pricing as starting points, while scopes/costs/terms are held; existing governed buyer outreach handles exact send approvals and deduplication. No outbound release inherited from the bridge.
5. Existing payment/settlement evidence reconciles independently before realised revenue is reported. Do not turn a citation, enquiry, unsigned proposal or forecast into booked income.

## Limits

The original PR receipts date to 11 October: provider SENT labels are not delivery or replies. The canonical Revenue Distribution snapshot was from earlier October and is historical. No live Gmail query, EmpireDB query, live current SEO ranks, live third-party editorial placement checks or production CRM sync is performed by this stage. Existing `/commercial` enquiry policy and CRM authentication must be read back separately before any private console or external workflow activation.

## Existing Marketing / SEO department integration (isolated branch only)

The existing `scripts/review_seo_department_integrated_20261018.py` now accepts optional flags `--earned-media-advisory`, `--earned-media-pr-root` and `--earned-media-distribution-root`, returning the new `earned_media_advisory` section within its existing read-only response. On 25 October this optional combined invocation returned 4 PR, 3 editorial, 4 consultancy and 1 proposal review items; the parent SEO department separately returned `HELD_UNVERIFIED_DEPENDENCY`. Neither result authorises publishing or CRM changes.

A fresh read of the two exact original Gmail threads on 25 October found one SENT message in each and no reply in either thread. This is not a full mailbox search, delivery confirmation, or proof an editor saw the message. Two other PR outlets remain research candidates, not approved next sends.

QA: 67 relevant bridge/SEO/editorial regression tests passed. Isolated branch integration is source-staged and has not been merged into `/srv/empire_os`; active production continues without a new runtime, schedule or endpoint. Existing founder authentication and canonical CRM matching are separate gates for an approved future private console release.

## Stage 2: internal Founder API and CRM match preview

- New router `empire_os/founder_earned_media_api.py` is mounted in the existing loopback Founder service under GET `/v1/founder-earned-media/review`, with `EMPIRE_EARNED_MEDIA_FOUNDER_READ_ENABLED` disabled by default. No canonical reads or writes, outbound or publication.
- Staged founder UI at `apps/search-command-centre/src/app/founder/earned-media/page.tsx` is 404 unless `EMPIRE_EARNED_MEDIA_FOUNDER_UI_ENABLED=1` and `EMPIRE_FOUNDER_CONSOLE_PRIVATE_AUTH_VERIFIED=1`. Those flags are **not authentication**; they must not be enabled or the change deployed until existing founder ingress/session authority is independently proven. There is no new public main-site link.
- `empire_os/earned_media_crm_match_preview.py` is an in-memory exact-join classifier, with no EmpireDB driver. It accepts separately owner-validated canonical tenant/company/prospect/opportunity identifiers and a reconciled original Gmail thread. Mismatched tenants, partial proofs, unknown sources or conflicting matches remain held. Even one apparent match is only a candidate requiring owner review, not permission to write Smart CRM.
- Two original press threads remain historical receipts, not fresh Gmail observations. No automatic follow-ups, scheduler, new agents, sales pipeline writes, revenue attribution or deployment.
