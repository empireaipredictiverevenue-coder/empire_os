# National Storm Hub — Build agent operating contract

This application is the existing Empire AI-operated National Storm Hub website.
**Continue and improve it, don't scaffold a replacement.**

## Production truth and scope

- Current website: `https://nationalstormhub.com`, hosted via its own loopback Next.js service and dedicated Cloudflare tunnel on EmpireOS.
- Existing source code: `apps/national-storm-hub/` and its current Git release/branch.
- Parent repo: EmpireOS with PostgreSQL **EmpireDB, not Supabase**.
- Follow the root `AGENTS.md` and all existing engineering approval gates. Development branches do not imply release consent. Avoid production modifications during research.
- Preserve previously built homepage, Storm Atlas, ZIP lookup, browser-local Passport, predictor, alerts centre, Texas and Florida hubs, research, recovery and founder Revenue Pulse.
- Keep verified official warnings separate from forecasts, observations, predicted commercial demand and paid revenue.
- No paid traffic, unsolicited outbound, payment activation or sale of homeowner data.

## Reuse — exact canonical SkillForge routing; do not duplicate skills

The owner is `empire_os/skill_exchange.py`. Use `recommend_work_item_skills` to discover relevant existing packs. Task components are exact identifiers; these mappings are **only suggestions**, not permission to load or execute an unapproved SKILL.md.

| Work being performed | Existing SkillForge component | Existing task/skill |
| --- | --- | --- |
| Source provenance / NWS weather evidence | `national_storm_hub_weather_evidence` | `empire-evidence-verification` |
| SPC/NWS forecasting and interpretation | `national_storm_hub_storm_predictor` | `empire-forecast-validation` |
| Website testing, rollback, guarded release | `national_storm_hub_website_release` | `empire-engineering-verification` |
| Original local SEO / AEO / GEO research | `national_storm_hub_seo_editorial` | `empire-seo-intelligence` |
| Authentic payments / Revenue Pulse evidence | `national_storm_hub_revenue_pulse` | `empire-revenue-reconciliation` |
| Repeat-to-skill review and independent outcomes | `national_storm_hub_skill_capture` | `empire-skill-authoring` |

**Do not invoke candidate skill instructions.** The current SkillForge approval registry may contain zero approved skills. Verify exact digest-pinned approval using the existing `empire_os.skill_trust` gate before a task is allowed to load a skill. Discovery is not approval. Never edit `config/skill_trust_registry.json` as a convenience.

## Reuse real operational code

- Historical classifier: `empire_os/storm_predictor.py`, which identifies NWS warning event types but does not verify household damage or buyer demand.
- Guarded forecast context: `empire_os/storm_intelligence_runtime.py` and `empire_os/storm_product_integration.py`; do not instantiate side-effecting agents on public requests.
- Existing site endpoints: `apps/national-storm-hub/app/api/alerts/route.js` and `app/api/predictor/route.js`. Do not add a second NWS or SPC pipeline without a specific evidenced deficiency.
- Existing browser-local Passport: `apps/national-storm-hub/app/page.jsx`. Do not claim that it is a cloud vault or tenant account.
- Protected founder financial read model: `app/api/founder/revenue-pulse/route.js`, sourcing the existing `runtime/revenue_pulse/latest.json` snapshot. Never represent EmpireOS-wide metrics as this brand's earnings or expose private data without authentication.
- Existing R&D + Innovator/Strategy Supervisor review: only research/approve through canonical owners; do not launch new queues, daemons or approval bypasses.

## Proof before launch

```sh
cd apps/national-storm-hub
npm ci
npm test
NEXT_TELEMETRY_DISABLED=1 npm run build
```

For production releases use the current guarded website rollback and public HTTPS smoke-check process. Test public `/alerts`, `/predictor`, `/research`, `/recovery`, `/states/texas`, `/states/florida`; private `/api/founder/revenue-pulse` must reject missing/wrong credentials with 401 and never disclose finances. The canonical Revenue Pulse timer already exists; **do not create another**.

## Repeat-to-skill

Record only verified independently completed work through the existing SkillForge observational pipeline; candidate drafts are not approved automatically. Review at least two distinct evidenced completions before drafting a new reusable procedure. Verify outcome improvements with independent holdout evidence and gain explicit digest-pinned approval before instructing production agents to load it.
