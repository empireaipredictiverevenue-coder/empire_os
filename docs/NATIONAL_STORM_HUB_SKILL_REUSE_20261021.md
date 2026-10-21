# National Storm Hub — reuse of existing EmpireOS skills

**Scope:** National Storm Hub web, forecasting, alerting, Storm Passport and protected Revenue Pulse.
**Date:** 2026-10-21
**State:** Exact SkillForge discovery routing added on isolated branch; **no skill approval or runtime execution**.

## Evidence

Actual EmpireOS SkillForge inventory observed on 2026-10-21:
- 13 local Empire-owned `SKILL.md` candidates under `empire_os/skills_library/skills/empire-*/`.
- `config/skill_trust_registry.json` contained **zero approved/pinned skills**. Candidate files are not permission to execute or inject agent instructions.
- Existing `empire_os/skill_exchange.py` discovers local skills by exact `target_component` keys and already includes task-to-role mapping.
- Existing `empire_os/skills_library.py` allows loading only pinned approved skills.
- SkillForge work completion observations, review-only proposals, holdout evaluation and promotion preflight already exist. This branch does not create or bypass them.

## Added exact component aliases to canonical SkillForge routing

| National Storm Hub component | Existing task | Existing skill |
| --- | --- | --- |
| `national_storm_hub_weather_evidence` | `evidence_analysis` | `empire-evidence-verification` |
| `national_storm_hub_storm_predictor` | `predictive_forecast` | `empire-forecast-validation` |
| `national_storm_hub_website_release` | `engineering_review` | `empire-engineering-verification` |
| `national_storm_hub_seo_editorial` | `seo_research` | `empire-seo-intelligence` |
| `national_storm_hub_revenue_pulse` | `revenue_reconciliation` | `empire-revenue-reconciliation` |
| `national_storm_hub_skill_capture` | `skill_authoring` | `empire-skill-authoring` |

For each future task, existing department/agent owners can pass the exact component key to `recommend_work_item_skills`. This chooses the local candidate and reports its digest **without dispatching jobs**. Nothing changes the approval registry. Do not create duplicate packs, a second Revenue Pulse timer or a duplicate alerts pipeline.

## Actually reused working components

- Reused existing `storm_predictor.py` NWS warning *classes* in the public read-only predictor; code is a JavaScript mirror and is not falsely described as a direct runtime import.
- Reused existing source-validated National Storm Hub `/api/alerts` and `/api/predictor` in the public site; no duplicate weather data fetch created here.
- Reused canonical EmpireOS Revenue Pulse V3 snapshot as **company-wide** private read model. NSH tenant revenue is unknown until source-bound payments exist.
- Reused existing browser-local Storm Passport area in public `/alerts`, where the user voluntarily chooses to follow the saved ZIP/state.
- Reused existing systemd National Storm Hub website service and tunnel; no new deployment or services created in this skill routing change.

## Test and no-overreach rules

```bash
cd /home/ubuntu/empire_worktrees/nsh_skill_reuse_20261021
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_national_storm_hub_skill_reuse.py \
  tests/test_skill_exchange.py tests/test_skill_trust.py
```

A passing test proves discovery routing and failure on untrusted instructions, **not** that skill quality or end-to-end automated execution has been proven. No live site, production service, skill digest approval, business customer, money or direct outbound is modified by this branch.

## Next actual website build priorities

1. Bring in original-source geospatial warning outlines with explicit NWS source dates rather than a decorative radar.
2. Read historic storm event evidence through existing storm modules and a verified NOAA archive adapter.
3. Continue optional browser alerts; do not advertise them as a guaranteed 24/7 emergency push channel.
4. Replace shared founder key with hardened identity/Cloudflare Access before broad private commercial access.
5. True first-party tenant-scoped traffic, enquiry and payment receipts when a verified, consented customer flow exists.

Existing skills govern HOW to do those things once approved; they are not substitutes for the finished features.
