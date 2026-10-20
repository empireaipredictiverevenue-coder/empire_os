# EmpireOS — Safe Predictive OBSERVE Release and Cross-Agent Integration Ownership

**20 October 2026 | Release coordinator: existing Predictive Intelligence owner**
**Goal:** Deploy a reproducible read-only commercial intelligence release **without merging into a dirty production checkout** or taking over other agents' source ownership.

## Current production evidence

- `/srv/empire_os` at inspection: git HEAD `398b186219645d7c2425bf504e1ab8e80b532534`, active branch `agent/data-cloud-wave4`.
- Production working tree has **193 uncommitted change rows**, including active code and commercial assets. A direct `git merge`, `git checkout`, `git reset` or deployment that overwrites production files **is not approved or safe**.
- Predictive feature branch at preparation, `76f035ffa2bc346c45afdbf348e83d1ba16dd5a6`, includes the new Tampa lead/material sourcing system plus earlier Finance, BLS, Storm, Newsjack, market-gap and profitability evidence modules. The feature branch is **not production**.
- The cross-agent board covers **20 priority owner worktrees**. Some have uncommitted source changes and several have modified paths overlapping with production. These owners need canonical merge reconciliation and proof checks, not blind cherry-picks.

## Release procedure (read-only versioned sidecar)

`scripts/prepare_predictive_readonly_release_20261020.sh` copies **committed HEAD only**, via `git archive`, to a new, commit-qualified folder:

```text
/home/ubuntu/empire_releases/predictive_observe_<commit-prefix>/
```

- Refuses a dirty Predictive source worktree and refuses to overwrite a previous release path.
- Stages the git archive in a fresh temporary directory under the same release root; only publishes it after extraction and checksum generation.
- Does **not** alter `/srv/empire_os`, git worktree branches, PostgreSQL, model registry, Finance, CRM, buyers, agents or systemd.
- Pins `metadata/source.txt` and SHA256 manifest for key executable/logic files. This is reproducibility protection, **not an independent cryptographic signature or source authenticity proof**.
- Includes an allowlisted `bin/empire-predictive-observe` launcher; it refuses arbitrary additional CLI args and always uses `--read-only`.
- Output is user-invoked: **no timer, HTTP server, background daemon, customer contact, RFQ, advertising budget, purchased inventory or production app mutation**.

**Explicit release workflow** after feature tests and git commit:

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
bash -n scripts/prepare_predictive_readonly_release_20261020.sh
bash scripts/prepare_predictive_readonly_release_20261020.sh
```

The command prints the exact pinned release path. Example one-shot review commands, replace `<release>` with that verified path:

```bash
<release>/bin/empire-predictive-observe commercial
<release>/bin/empire-predictive-observe finance
<release>/bin/empire-predictive-observe gaps
<release>/bin/empire-predictive-observe cost
<release>/bin/empire-predictive-observe measurement
<release>/bin/empire-predictive-observe sources
<release>/bin/empire-predictive-observe owners
```

`cost-sector` is **separately opt-in** and makes up to four bounded official BLS public HTTP GETs; it does not run as a default health check.

**Rollback:** because no running application or live service points to the release and production was not altered, simply stop invoking that release's launcher. Do **not** remove other agents' worktrees or alter existing services. A future official production rollout needs reviewed source merge, migrations, service and operating authority plans.

## Cross-agent acceptance and dependency board

`scripts/review_empire_cross_agent_release_board_20261020.py --read-only` inspects git metadata for:

- Predictive Intelligence / Cloud,
- Lead Supply, A2A Commercial Signal Miner, Buyer Scout and commercial buyer qualification,
- Agency acquisition and reply programmes,
- Finance foundation/custody and Revenue Fabric/Attribution,
- Data Brokerage, Solar marketing, local market intelligence, CRM and Storm.

Each owner retains its own source, merge and operational execution permissions. The integration coordinator can inspect commits, report dirty branches and path collisions, stage read-only release artifacts, run regressions and prepare an owner review queue. It cannot deem source semantics reconciled merely because Git reports no conflict.

**Evidence gate order for the multi-department commercial OS**:

1. **Canonical buyer and tenant identity** / provider-authenticated buying role and message ancestry.
2. **Consent, ZIP, duplicate, serviceability and exclusivity** for genuine lead inventory.
3. **Accepted customer price, contracts and verified fulfilment capacity**.
4. **Real supplier quotation, job-measured BOM, labour/delivery cost and finance refund/settlement**.
5. **Original registered Quant profit forecast prior to outcomes, immutable readback**.
6. **Source revision, rights, licensing, data quality, tenant and time-window consistency**.
7. **Predictive Cloud constrained shadow scenario compilation**; financial allocation only with explicit operational, finance, marketing and buyer authorisation.

Not-yet-verified data remains `null`, source research only. Draft owner-task idempotency does not prove dispatch or durable replay prevention.

## Controlled future production promotion

Before promoting any source-owner change to canonical production:
- capture current production commit and an independent secure backup/snapshot where appropriate;
- agree a single authorised release/merger owner and pause collisions rather than clobber active work;
- have owner confirm its exact source diff, version, tests, original source right/secret handling and migrations;
- reconcile shared-file modifications and single-writer Finance/Buyer/CRM/Marketing ownership;
- test a clean staging checkout, integrity and safety checks, permissions, rollback and smoke/health;
- obtain relevant explicit deployment approval for money/outbound/tracking/network services;
- validate readback/monitoring and source schema compatibility after deployment.

The present sidecar is **deployed read-only research capability**, *not* broad production feature integration or a live commercial fulfillment service.
