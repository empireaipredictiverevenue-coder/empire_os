# Empire Media OS Gap Map

Date: 2026-09-23  
Status: Phase A architecture audit / implementation map  
Authority: Blueprint v6 and verified live runtime remain production truth.

## Decision rule

Every requested Media OS capability is classified before implementation:

- **REUSE** — canonical EmpireOS capability already owns the job.
- **ENHANCE** — extend an existing canonical capability.
- **MERGE** — salvage useful prior implementation into the canonical system.
- **NEW** — genuine media-specific capability does not exist canonically.
- **ARCHIVE** — preserve prior work as recovery memory; do not run it as canonical.
- **REJECT** — do not implement the approach because it violates truth, quality, licensing, architecture, or governance.

Media OS is an extension of **Marketing & Growth** and the Predictive Cloud **Search / Attention / Recommendation** layer. It is not a new department, new brain, new evidence store, or new authority system.

## Verified canonical systems to reuse

- Astra Executive — evidence-typed coordination and founder gates.
- Control Fabric — events, dependencies and authority.
- Intelligence Fabric — shared graph/provenance layer.
- Quant Brain / Predictive Intelligence — uncertainty, economics, risk, VOI and portfolio ranking.
- Opportunity Factory / Opportunity Loop — evidence-first commercial opportunity lifecycle.
- Market Sweeps / Revenue GPS — evidence-backed market observations.
- Revenue Pulse — observed commercial truth, separate from forecasts.
- Search Intelligence / Search Fabric — search/AEO/GEO/organic evidence and opportunity.
- Competitor Audience Intelligence — public competitor/audience evidence.
- Community Intent — public community pain/intent observations.
- Voice Lab — self-hosted STT/TTS foundation.
- Model Registry / Intelligence Router — provider/model selection.
- Experiment Intelligence — experiment/causal review.
- Revenue CRM / Conversion Intelligence — lead/customer/funnel state and attribution inputs.
- Founder Console — canonical top-level operating surface.
- Marketing & Growth department — content/editorial, brand/creative, organic distribution and attribution owner.

## Salvage audit

Historical Empire code contains useful media predecessors, but they are **not canonical production truth**:

- Historical commit `e2f2306`: `content_engine.py`, `video_engine.py`, `content_pipeline.py`.
  - Useful: FFmpeg rendering pattern, deterministic pipeline shape, round-robin work queue concept.
  - Reject/retire: hard-coded `/root/empire_os` paths, direct provider secret reads, SQLite shadow content store, silent text-slide “video” as final-quality output, template fallback claims not backed by evidence, direct distribution assumptions.
  - Classification: **MERGE structural lessons + ARCHIVE implementation**.
- Historical `social_syndication.py`:
  - Useful: draft queue, multi-platform aspect presets, footage repurposing concept.
  - Reject/retire: direct model/provider routing, stale provider assumptions, publish adapter living outside current governance.
  - Classification: **MERGE draft/adapter ideas + ARCHIVE implementation**.
- Historical `creativeAssetLibraryService.ts` inventory proves an asset/versioning system existed in an earlier codebase.
  - Classification: **MERGE schema concepts after source-level recovery review; do not recreate blindly**.
- Historical July 2026 commits contain `skills_library/`, `*_SKILLS.md`, SOUL files and shared agent guardrails.
  - Useful: explicit skill procedure contracts, artifact-only/read-only guardrail modes, bounded execution, testable output shapes.
  - Reject/retire: old `/root/empire_os` paths, PM2-era runtime assumptions, stale provider/model routing and autonomous agent sprawl.
  - Classification: **MERGE skill-candidate/guardrail concepts + ARCHIVE legacy runtime**. Current Media OS emits skill candidates only; it does not recreate a parallel live skill registry.

## Requirement classification

| # | Requirement | Class | Canonical owner / implementation decision |
|---:|---|---|---|
| 1 | Connect to existing Empire intelligence | REUSE + ENHANCE | Control Fabric events/adapters; no shadow intelligence systems. |
| 2 | Empire Attention Graph | ENHANCE + NEW | Extend Intelligence Fabric with media node/edge types and read projections; no second graph database. |
| 3 | Media Opportunity Graph | ENHANCE + NEW | Intelligence Fabric + Opportunity Factory + Quant Brain feature packet/ranking. |
| 4 | Channel Portfolio | REUSE + ENHANCE | Strategy + Marketing channel portfolio; flagship first, evidence-gated expansion. |
| 5 | Channel Spawning Engine | NEW | Candidate evaluator only; 30–50 credible ideas and evidence required; public launch is founder gate. |
| 6 | YouTube Intelligence Node | NEW | Authorised/public YouTube adapter emitting canonical observations into Intelligence Fabric. |
| 7 | Outlier Engine | NEW | Media-specific baseline/outlier detector; observations feed Quant/Opportunity, not automatic content copying. |
| 8 | Trend Fusion Engine | MERGE + ENHANCE | Fuse existing Search, Community, Competitor, CRM, buyer conversation and market signals; no new crawlers by default. |
| 9 | Voice-of-Buyer connection | REUSE + ENHANCE | Conversation OS, CRM, Community Intent, reviews/search/comments adapters. |
| 10 | Video Idea Factory | NEW + ENHANCE | Media-specific idea object; use Opportunity/Quant scoring rather than parallel economics. |
| 11 | Content Franchise Engine | NEW | Detect repeatable formats from owned performance; correlation labelled as such. |
| 12 | Research & Evidence Pack | ENHANCE + NEW | Media-specific research package referencing canonical evidence/provenance; no new evidence store. |
| 13 | Fact Freshness Engine | NEW + ENHANCE | Media claim freshness policy linked to existing evidence timestamps/refresh infrastructure. |
| 14 | Script Engine | NEW + ENHANCE | Media skill using canonical evidence packs and existing model routing. |
| 15 | Storyboard + Shot List | NEW | Deterministic media artifact derived from approved canonical content object. |
| 16 | Visual Director | NEW + ENHANCE | Media planner using Model Registry/Intelligence Router and real Empire assets first. |
| 17 | Cinematic Film-Look Engine | NEW | Reusable direction/style contract; deterministic continuity controls. |
| 18 | Premium Thumbnail Factory | NEW | 6–12 internal concepts, 2–3 surfaced candidates, quality/similarity/mobile checks. |
| 19 | Title + Thumbnail Pairing | NEW | Joint creative package/experiment unit. |
| 20 | Title Engine | NEW | Search-led and browse-led candidates; evidence/brand constraints. |
| 21 | Description / SEO / Metadata | REUSE + ENHANCE | Search Intelligence + Marketing content contracts; tags remain low priority. |
| 22 | Open-source-first strategy | REUSE + ENHANCE | R&D build/buy/open-source review + Model Registry licence gates. |
| 23 | Model Registry | ENHANCE | Extend existing `ModelRegistry`; do not create a Media-only registry. Add media task/license/VRAM/benchmark metadata. |
| 24 | Provider fallback | ENHANCE | Intelligence Router/provider adapters; modality-specific primary/secondary/fallback policy. |
| 25 | Model Benchmark Arena | ENHANCE + NEW | R&D evaluation lifecycle + media benchmark suite; shadow validation before promotion. |
| 26 | Motion Design System | NEW | Code-defined reusable motion primitives. |
| 27 | Watermark + Brand System | ENHANCE | Existing Brand/Creative ownership plus media overlay rules. |
| 28 | Channel Brand Generator | NEW | Draft-only generator; meaningful public brand/channel launch is founder gate. |
| 29 | Subscriber Animation System | NEW | Contextual reusable motion components; no arbitrary repetitive prompts. |
| 30 | Audio System | REUSE + ENHANCE | Voice Lab for STT/TTS; add narration profiles, mastering, ducking, sync and QC. |
| 31 | Audio Branding | NEW | Rights-tracked motifs/stings owned by Brand/Creative. |
| 32 | AI Video Timeline | NEW | Canonical deterministic timeline schema consumed by renderers. |
| 33 | Render Engine | MERGE + NEW | Salvage FFmpeg renderer concept; create provider-agnostic renderer abstraction. |
| 34 | Render Farm / Queue Manager | NEW | Design now; material GPU/cloud provisioning remains founder/spend gate. |
| 35 | Creative Asset Library | MERGE + ENHANCE | Recover old asset/versioning schema; add rights/provenance/quality/usage; no shadow media store. |
| 36 | Evidence-to-Visual Engine | NEW + ENHANCE | Convert canonical Empire evidence into charts/maps/diagrams with provenance. |
| 37 | Shorts Engine | NEW | Candidate extraction + standalone-value test; no blind clipping. |
| 38 | Shorts → Long-form Funnel | NEW + ENHANCE | Analytics/attribution journey projection. |
| 39 | Canonical Content Object | NEW | One evidence-linked source object for all derived media. |
| 40 | Repurposing Engine | MERGE + NEW | Salvage historical repurposing concepts; derive from canonical content object. |
| 41 | Content Knowledge Graph | ENHANCE | Media node/edge view inside Intelligence Fabric, not a second graph. |
| 42 | Duplication Guard | NEW | Topic/title/hook/visual/footage similarity and repetition registry. |
| 43 | Competitor Audience Intelligence | REUSE + ENHANCE | Existing competitor audience runtime/research executor; add YouTube public evidence adapter. |
| 44 | Comment Intelligence | ENHANCE + NEW | New YouTube comment adapter feeding existing Voice-of-Buyer/Community/Opportunity systems. |
| 45 | Comment Response System | NEW | Draft → brand/policy check → governed publish; no autonomous spam. |
| 46 | Owned Audience Capture | REUSE + ENHANCE | Demand Genesis, CRM, landing/product surfaces and consent/attribution. |
| 47 | Search / SEO Connection | REUSE + ENHANCE | Search Intelligence canonical keyword/intent/product map plus media linkage. |
| 48 | Analytics Ingestion | NEW | Authorised YouTube Analytics adapter; richer owned metrics only where permitted. |
| 49 | Retention Intelligence | NEW | Align retention with transcript/scene/timeline; explanations remain hypotheses until tested. |
| 50 | Empire Viral Genome | NEW | Creative-feature/outcome dataset; no causal claims from correlation alone. |
| 51 | Experiment Engine | REUSE + ENHANCE | Existing Experiment Intelligence owns experiment truth; add media experiment schema. |
| 52 | Explore / Exploit allocation | REUSE + ENHANCE | Quant Brain portfolio policy; initial 70/20/10 is a hypothesis, not hard-coded truth. |
| 53 | Audience Cluster Model | NEW + ENHANCE | Media audience clusters as Intelligence Fabric projections; validate from observed data. |
| 54 | Viewer Journey Graph | ENHANCE + NEW | Intelligence Fabric + Conversion/CRM attribution edges, privacy-compliant and evidence-bounded. |
| 55 | Revenue Attribution | REUSE + ENHANCE | Revenue Pulse remains revenue truth; Media OS may supply source/evidence links only. |
| 56 | Content Value Score | NEW + ENHANCE | Quant feature/decision packet combining attention, commercial outcomes and cost; unknowns remain null. |
| 57 | Monetisation Engine | REUSE + ENHANCE | Product catalog/Marketing/Revenue systems; media maps topics to existing offers and verified outcomes. |
| 58 | Sponsor Intelligence | NEW | Future research/package prep; outbound/contracting governed. |
| 59 | Creator Collaboration Engine | NEW | Public relevance research; collaboration outreach governed and non-spam. |
| 60 | Localisation Engine | NEW | Activate only after English evidence; licence/market/quality gates. |
| 61 | Content Moat | REUSE + ENHANCE | Prioritise proprietary Empire builds/data/experiments through Idea Factory/Quant. |
| 62 | Build-in-Public Pipeline | NEW + MERGE | Adapter from build/change events into media opportunity candidates. |
| 63 | Empire Build Journal | NEW | Evidence-linked change journal; source material only, not automatic factual marketing claims. |
| 64 | Content-to-Product Incubator | MERGE + ENHANCE | Audience pain signals feed Opportunity Factory/Quant/Product; no duplicate incubator brain. |
| 65 | Failure Learning | NEW + ENHANCE | Media outcome taxonomy stored as learning evidence; feed experiments/Cortex. |
| 66 | Audience Trust Metrics | NEW + ENHANCE | Analytics/feedback quality layer; prevent CTR-only optimisation. |
| 67 | Cost Governor | MERGE + ENHANCE | Quant Brain + capital/cost policy; add GPU/render/API cost estimates. |
| 68 | Portfolio Capital Allocation | REUSE + ENHANCE | Capital Allocator + Quant Brain; media adds candidate resources, not a second allocator. |
| 69 | Content Kill / Pivot Rules | NEW + ENHANCE | Strategy/Quant policy based on rolling evidence, not sunk-cost automation. |
| 70 | Rights / Provenance Registry | MERGE + NEW | Extend recovered asset-library concept with licence/rights/model/workflow provenance. |
| 71 | Synthetic Media Policy | NEW | Disclosure/authenticity policy integrated into QC/publish gate. |
| 72 | Quality Control Gate | NEW + ENHANCE | Deterministic video/audio/text/thumbnail/brand/content checks plus evidence verifier. |
| 73 | Disaster Recovery / Reproducibility | REUSE + ENHANCE | Existing recovery discipline plus media manifests/assets/model/workflow versions. |
| 74 | Publishing Calendar | NEW | Shared schedule/read model; publishing remains governed. |
| 75 | Rapid Response Lane | NEW + ENHANCE | Priority lane using existing trend/evidence systems; accuracy gate remains mandatory. |
| 76 | Evergreen Lane | NEW | Scheduling/content portfolio classification. |
| 77 | Content Refresh Engine | NEW + ENHANCE | Search decay + freshness + owned analytics drive refresh candidates. |
| 78 | Content Decay Detection | ENHANCE + NEW | Reuse Search content-decay concepts; add YouTube rolling baselines. |
| 79 | Skill-first media automation | REUSE + ENHANCE | Preserve Astra/Control Fabric skill-first pattern; no hundreds of new agents. |
| 80 | Media Skill Registry | ENHANCE | Reuse existing Empire skill infrastructure after current registry/location audit; do not create a parallel skill store. |
| 81 | Media Skill Compiler | NEW + ENHANCE | R&D/experiment lifecycle: observe → tests → replay → shadow → version/register; no self-production mutation. |
| 82 | Workflow Evolution | REUSE + ENHANCE | R&D + Experiment Intelligence promotion lifecycle. |
| 83 | Founder Console | REUSE + ENHANCE | Add Media OS projection to canonical Founder Console; specialist views only as drill-down. |
| 84 | Natural Language Control | REUSE + ENHANCE | Astra/Hermes/control routing translates founder requests into media skills; authority unchanged. |
| 85 | 90-day Plan | REUSE + ENHANCE | Adopt as staged operating plan; volume ranges are planning targets, quality/evidence gates override them. |
| 86 | Subscriber Milestones | NEW | Measurement/review milestones only; no guaranteed date forecasts. |
| 87 | Scale Model | REUSE + ENHANCE | Strategy channel/audience portfolio; evidence decides expansion. |
| 88 | Governance | REUSE | Existing Control Fabric/Astra/founder gates remain authoritative. |
| 89 | Absolute Rules | REUSE + ENHANCE | Encode in Media policy/QC; no fabrication, plagiarism, fake engagement, unlicensed assets or AI sludge. |
| 90 | First Implementation Action | REUSE + NEW | This Gap Map is the output; audit precedes code. |
| 91 | Recommended Build Order | REUSE | Accepted as phases A–P; Phase A is current. |
| 92 | Definition of Done / strategic intent | REUSE | Acceptance contract: evidence → premium content → governed publish → measured response → learning → product/revenue linkage. |

## Explicit ARCHIVE / REJECT decisions

### ARCHIVE
- Historical autonomous `content_engine.py` as a production content author.
- Historical `content_pipeline.py` as a cron-driven autonomous publisher/distributor.
- Historical `video_engine.py` as a final-quality video engine.
- Historical `social_syndication.py` as a canonical publisher/model router.
- Any SQLite-only media state that would shadow Supabase / Intelligence Fabric / canonical runtime evidence.

### REJECT
- Generic template claims presented as verified facts.
- A “faceless content farm” architecture.
- Creating one agent per media subtask when a skill + deterministic tool suffices.
- Automatic public publishing merely because generation succeeded.
- Automatic channel spawning.
- Automatic material GPU/cloud spend.
- Copying competitor scripts, thumbnails, footage or proprietary creative.
- Synthetic events presented as real footage.
- Model/provider use without recorded commercial permission and attribution requirements.
- Treating views/subscribers as revenue.
- Treating correlation in creative performance as causation.
- Using FLUX.1 [dev] weights in Empire commercial production under the current non-commercial model licence without a separate permitted commercial path.

## Open-source licence audit — initial

This is an engineering classification, not legal advice. Exact versions/build flags must be recorded in the rights/provenance registry before production.

| Component | Initial decision |
|---|---|
| FFmpeg | **REUSE** as renderer foundation. Default FFmpeg is LGPL 2.1+; GPL-enabled builds change obligations. Record build flags and linked libraries. |
| OpenCV 4.5+ | **REUSE** for image/video analysis under Apache-2.0. |
| Whisper | **REUSE/ENHANCE** where needed; code package is MIT. Existing Voice Lab already supplies STT, so do not duplicate by default. |
| PySceneDetect | **REUSE** candidate for shot/scene analysis; BSD-3-Clause. |
| ComfyUI | **OPTIONAL ADAPTER / REVIEW**. GPLv3. Prefer process boundary/workflow integration and review distribution obligations before embedding. |
| Wan2.1 | **MODEL CANDIDATE**. Repository states Apache-2.0 for models; benchmark/licence record still required per exact artifact. |
| HunyuanVideo | **MODEL CANDIDATE / REVIEW**. Uses Tencent Hunyuan Community License, not automatically treated as Apache-style commercial permission. |
| FLUX.1 schnell | **MODEL CANDIDATE**. Apache-2.0 and described by BFL as commercial-use capable. |
| FLUX.1 dev / Krea dev / Kontext dev | **REJECT for default commercial local production** under current non-commercial model licence unless a separate commercial licence/path is verified. |
| Remotion | **OPTIONAL LICENSED ADAPTER**, not assumed free/open-source infrastructure for company automation; current commercial automation pricing/licensing applies. |

## Phase A implementation decisions

Build now:

1. Register `media_os` as a canonical Control Fabric component owned by Marketing & Growth.
2. Add an evidence-preserving Media OS foundation contract.
3. Define canonical content/evidence objects that reference existing evidence rather than copying it into a shadow store.
4. Add media opportunity feature packets for Quant/Opportunity ranking without claiming a score is revenue.
5. Add channel-launch candidate gating and publishing authority rules.
6. Surface Media OS foundation status in Founder Console.
7. Add architecture tests proving:
   - Media OS is owned by Marketing & Growth.
   - it depends on existing systems;
   - it cannot publish;
   - it cannot launch a new channel;
   - it cannot commit material GPU spend;
   - subscriber milestones are targets, not forecasts;
   - factual claims require evidence references.

Do not enable yet:

- public auto-publishing;
- public comment posting;
- new-channel creation;
- material GPU/cloud render commitments;
- sponsor/collaboration outbound;
- binding media commercial contracts.

Those remain governed/founder gates under Blueprint v6.
