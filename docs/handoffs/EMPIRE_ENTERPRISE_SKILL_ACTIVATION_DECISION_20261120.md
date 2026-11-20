# Empire AI — SkillForge enterprise acceptance decision

Date: 20 November 2026. Owner: existing SkillForge and EmpireOS department execution plane. Scope: read-only review of selected enterprise portfolio skills.

**Decision:** 8 Empire-authored skills have passed in-memory loading under temporary process-local pins. They are **not approved**, have **not run as production agents** and must not be placed into the live trust registry until the original promotion requirements are actually evidenced.

## Direct verification

- Canonical `scripts/verify_skillforge_completion.py --gauntlet` returned **541 passed / 1 warning**, **24 test groups**, **9/9 engineering checks PASS** (exit 0).
- Extended targeted security, trust, routing, promotion, holdout and completion tests returned **54 PASS** following real-case indexing; previous security regression batch returned 102 PASS.
- `runtime/skillforge/observations`: 1,872 existing provenance-validated learning observations, 0 invalid and no truncation. These are **not independently graded outcomes**.
- `runtime/departments/work/done`: 2,514 completed queue records. Direct-component and department-only source scopes were sampled into a total of **57 real work review cases**, without copying raw records.
- Live trust registry remains unmodified: **zero approved skills**. The real `inspect_department_skill_context.py` returned zero agent-loadable skills and correctly rejected unapproved candidates.
- No production service change, merge, commit, deployment, migration, outbound, payments, or customer data export. Existing shared worktree is dirty and must be preserved.

## Exact digest candidates, available for independent review, not approved

| Skill | Exact source SHA-256 | Source cases (queue status only) | Acceptance status |
|---|---|---|---|
| `empire-evidence-verification` | `f14e5ddd4eaaad69847ba7c9c15815a929e83b9ec244721a1a6f88362af86d9b` | DONE 217, BLOCKED 0, FAILED 0 | Isolated loading PASS; independent quality review OPEN |
| `empire-fulfilment-verification` | `7700a8f87e4459b5648113e9abfcbe56e6d9b3495a17e16fdcd5c928e7a4b81b` | DONE 17, BLOCKED 405, FAILED 0 | Isolated loading PASS; independent quality review OPEN |
| `empire-identity-resolution` | `61990757bd4b6774d2338bc3761256ab8abefc68e8afc49f3167ac18b4e8be07` | DONE 367, BLOCKED 2, FAILED 44 | Isolated loading PASS; independent quality review OPEN |
| `empire-lead-research` | `612fae0277d80374a1f3254a11a9b2d3a0551bfb8f0b5b311843e90716df6c99` | DONE 184, BLOCKED 0, FAILED 0 | Isolated loading PASS; independent quality review OPEN |
| `empire-product-catalog-verification` | `6dfe8ce9502e0073da70fdd5f27e84516370feb4f5368a93fbff21115cda2ef5` | DONE 858, BLOCKED 0, FAILED 3 | Isolated loading PASS; independent quality review OPEN |
| `empire-revenue-reconciliation` | `43444c9804cdf42ddf934272470d70d5e555a524b244bf0412af46c5f6e4436a` | DONE 4, BLOCKED 0, FAILED 0 | Isolated loading PASS; independent quality review OPEN |
| `empire-seo-intelligence` | `989c9fafdce2aeeebb662aeb9143be216bb0d3225a85ffc7dbee6b3c1d267dcb` | DONE 86, BLOCKED 0, FAILED 0 | Isolated loading PASS; independent quality review OPEN |
| `empire-skill-authoring` | `55a772ca4f50e05206c1a6aeaa3b973226472156295df12b2a471b90ec64a8ba` | DONE 7, BLOCKED 2, FAILED 1 | Isolated loading PASS; independent quality review OPEN |

**No independent holdout has passed.** The 57 source records are a reviewer intake inventory; a queue `DONE` state is not a correct decision label. The paired holdout scorer requires at least 10 cases with 2 negatives, 2 improvements, no regressions, and 90% candidate accuracy, plus separately verified labels. Historical cases must be reviewed by an independent reviewer against their source receipts. We must measure the same real agent workflow with and without the skill, not manufacture baseline or candidate outcomes.

## Remaining eight held candidates

`empire-engineering-verification` (concurrent modification); `empire-scientific-evidence-diligence` (untracked candidate); `pdf` and `xlsx` (Anthropic service-specific terms); `doc-coauthoring` (licence not locally evidenced); `frontend-design`, `webapp-testing`, `skill-creator` (Apache 2.0 licence files; independent script safety and suitability evaluation needed). No third-party script executed.

## Promotion criteria, preserved from the existing canonical SkillForge owner

1. Independently verify held-out labels and original source evidence for each eligible skill.
2. Reproduce baseline and skill-enabled outputs through real authorised agents in an isolated environment; record outputs with exact skill hashes and regression count.
3. Independently review tenant boundaries, privacy, injection risk, legal licence and ownership.
4. Ask for founder approval of the **exact, unchanged candidate digest** only after gates 1–3; record the reviewed signed decision in source control through existing owner.
5. Verify the activated trust registry and agent context readback through existing SkillForge, then compare customer-facing work against actual approved requirements.

## Next safe action

Existing QA/SkillForge owner: take the 57 hashed source-case references from `docs/handoffs/EMPIRE_ENTERPRISE_SKILL_SECURITY_REVIEW_20261120.json`, inspect underlying canonical receipts in the secured environment, independently label applicable positive and negative decisions, then run a bounded paired evaluation. No approval or production changes before passing the gates. The missing independent evidence must not be replaced with synthetic labels or inferred approval.

## Reproduction commands (EmpireOS, read-only and local test only)

`/srv/empire_os/.venv/bin/python -B scripts/verify_skillforge_completion.py --gauntlet`

`/srv/empire_os/.venv/bin/python -B -m pytest -q tests/test_enterprise_skill_security_preview_20261120.py tests/test_enterprise_skill_selection_20261119.py tests/test_skillforge_benchmark.py tests/test_skillforge_promotion.py tests/test_skill_trust.py tests/test_skillforge_completion.py`

**Current classification: TESTED IN ISOLATION / NOT INDEPENDENTLY QUALITY VERIFIED / NOT FOUNDER APPROVED / NOT LIVE.**

## 20 November — deduplicated real-case evidence replay (supersedes 57-case intake)

Existing SkillForge evaluation was extended *without modifying the production trust registry*. Historical work records were grouped by hashed substantive request input (`target_component`, `action`, `intelligence_request`, `memory_query`, `success_condition`, `authority`), excluding work ID and queue status. This prevents repeated task executions from inflating holdout case counts.

- Deduplicated review selection: **64** canonical work-record snapshots; **all 64 source-record SHA-256 hashes replayed successfully** against current disk bytes. This verifies historical queue-record integrity, **not underlying source receipt authenticity or outcome accuracy**.
- **56** completed records have result-evidence references with no queue error; these are *positive source-review candidates*, not independently correct outcomes.
- **8** blocked/failed records have no result-evidence references; these are *negative source-review candidates* awaiting independent investigation, **not verified safety holds**. Do not use the queue state as a gold label.
- Critical dataset diversity: identity resolution has **413** historical work records across statuses but only **2 unique request shapes**; CommerceOS catalogue has **861 records / 10 shapes**; fulfilment has **422 / 4 shapes**. These repetitions must not be sold as independent evaluation evidence.
- The existing `promotion_preflight(...)` independently read back **BLOCKED for all 8** shortlisted, internally authored skill candidates: no verified independently labelled holdout supplied. **Zero skill approvals** were applied.
- Additional regression run **57 PASS**. The canonical SkillForge gauntlet from this session remains **541 PASS / one warning** and **9/9 engineering acceptance checks PASS**. These measure engineering contract readiness, **not skill quality or live adoption**.
- Updated machine-readable source evidence and exact promotion blockers: `docs/handoffs/EMPIRE_ENTERPRISE_SKILL_SECURITY_REVIEW_20261120.json`.

**Current next safe operation:** Independent owner must inspect first-party source receipts and disputed negative cases, then provide genuine blind labels and observed paired baseline/candidate outcomes through the original SkillForge benchmark contract. Do not manufacture 10-case suites from repeated historical runs or promote based on this source audit. No founder command is needed to complete the current read-only source audit. Production registry remains unchanged.

## 20 November — founder-directed live advisory skill use

Founder explicitly directed actual activation. This **supersedes previous zero-pin and isolated-preview status** without claiming independent model improvement, completed customer actions or tool authority. The repository's live trust registry now has **12 exact SHA256-pinned advisory skills**: the prior 8 Empire-authored skills plus `empire-engineering-verification`, `empire-scientific-evidence-diligence` and local Apache-2.0 `frontend-design` and `webapp-testing`. The two internal source files are included in this scoped release so the registry is reproducible, preserving the founder engineering evidence contract and original scientific research rights limits.

Existing `empire_os/department_worker.py` now passes the selected **whole, untruncated, digest-verified advisory text** to existing Empire Coder PLAN objectives for that task's exact component/department. It records `skill_instruction_context_loaded`, selected names and SHA256 digests on the existing job/result. Only the original Coder and its original queue/permissions execute; no added scheduler, sender, publisher, provider, DB migration, shell or agent. Existing `SyntheticAgent` role loader accepts the longer engineering pack without truncation. UI tasks prefer the approved frontend-design pack; exact browser-review actions prefer webapp-testing. Original tenant, spend, send, deployment and founder gates remain independent.

Four external candidates remain **unapproved and not executed**: bundled `pdf`/`xlsx` are subject to an Anthropic-specific agreement not independently cleared for the EmpireOS runtime; `doc-coauthoring` has no local verified licence and exceeds the 12KB agent context limit; `skill-creator` exceeds that limit. Existing internal PDF evidence bridge, data reconciliation and SkillForge remain available. No raw data acquisition or script execution is granted through any skill.

The canonical SkillForge completion validator was boundedly adapted to admit **only the two exact-name Apache-licensed advisory text bundles**. Any other third-party approval, bad digest, missing licence or unknown scope fails. This is an **instruction-content activation**, not independent skill quality approval. Verified production Coder-job outcomes must be checked separately; do not imply models followed the text merely from an agent-loader smoke test.
