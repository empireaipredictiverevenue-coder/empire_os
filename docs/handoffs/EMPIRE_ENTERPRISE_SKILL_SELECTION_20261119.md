# Empire AI — enterprise-wide existing skills selection

Status: INVENTORY_VERIFIED / SELECTION_REVIEWED / NO_LIVE_ACTIVATION
Date: 2026-11-19. Owner: Existing EmpireOS orchestration and SkillForge; founder retains release authority.

## Source-of-truth findings

The server has 33 local SKILL.md files under `empire_os/skills_library/skills/` (including 16 Empire-specific skills). `empire_os/skill_exchange.py` already provides exact task/department selection, returns `OBSERVE`, and does not execute or download skills. Do not add another orchestrator, skill registry, scheduler or unsafe automatic selection. The shared production worktree contains unrelated uncommitted work; preserve it.

## Priority portfolio — all Empire AI businesses

| Priority | Existing skills | Existing business owner/use | Evidence required for next promotion |
| --- | --- | --- | --- |
| P0 | empire-revenue-readiness; empire-revenue-reconciliation | Sales Director, Predictive Revenue, Smart CRM, FinanceOS | Real buyer/contract/payment and first-sale evidence, no simulated revenue |
| P0 | empire-lead-research; empire-identity-resolution; empire-reply-triage; empire-commercial-email-copy | Buyer Scout, CRM, Sales Director, relationship-first outbound | Official company/person identity, existing-contact/suppression check, verified replies, human approval before send |
| P0 | empire-engineering-verification; webapp-testing | EmpireOS, Codex/FreeBuff, DesignOS, website and CommerceOS | Real browser screenshots, regression tests, guarded live readback and rollback |
| P1 | empire-search-source-reliability; empire-evidence-verification | Search Fabric, Knowledge Factory, legal/property/scientific data brokerage | First-party provenance, freshness, dedupe, rights and buyer-useful coverage |
| P1 | pdf; xlsx; docx | Knowledge Factory, Data Brokerage, FinanceOS, scientific/legal procurement research | Page-/cell-level source attribution, layout/table accuracy, rights and tenant boundary |
| P1 | empire-seo-intelligence; doc-coauthoring | SEO Director, MediaOS, blog, product pages | Search/indexing outcomes, trustworthy copy, actual qualified demand |
| P1 | empire-product-catalog-verification; empire-fulfilment-verification | CommerceOS, Predictive Cloud catalogue, customer delivery | Authorized supplier/product and real fulfilled-order verification |
| P1 | empire-forecast-validation; empire-scientific-evidence-diligence | Predictive Revenue/Cloud and Scientific Intelligence | Genuine forecast/outcome pairs, methods, replication and data rights |
| P1 | frontend-design; canvas-design; pptx | DesignOS, MediaOS, brand, proposals, sales collateral | Compare renders against founder-approved brand references |
| P2 | mcp-builder; skill-creator; empire-skill-authoring | Existing integration owners and SkillForge | Security review, isolated evaluation and existing dispatcher ownership |
| P2 | empire-affiliate-publisher-operations | Awin/affiliate operations | Verified publisher/advertiser terms and actual transactions |

## Exclusions / avoid accidental adoption

`brand-guidelines` applies Anthropic branding, not the Empire AI visual system. Do not apply it to Empire public artifacts. `slack-gif-creator`, `algorithmic-art`, and generic `theme-factory` are task-specific rather than enterprise default skills. `web-artifacts-builder` is a candidate for isolated UI work, not an alternative to DesignOS or the live website pipeline. Third-party skill scripts are untrusted until reviewed.

## Bounded validation in this chat

- Existing PDF skill and **33** local skills enumerated on EmpireOS (16 Empire-authored).
- Existing exact skill-selection contract read and preserved.
- PDF reader accessed a real 22-page internal PDF and returned source page text.
- Read-only `empire_os/knowledge_factory_pdf_bridge.py` added with page hash, document hash, tenant boundary, noncanonical stage and disabled commercial reuse.
- `tests/test_knowledge_factory_pdf_bridge.py` and existing intake/SkillForge tests: 34 PASS.
- Python PDF extraction libraries absent in `/srv/empire_os/.venv`; remote document reader exists, but automated end-to-end source mining and table extraction are NOT verified.

## Follow-up execution in the same chat — scoped enterprise integration

- Added eight exact, portfolio-wide workflow selectors in `empire_os/skill_exchange.py` for relationship-first buyer research, document research, scientific diligence, finance source documents, UI verification, editorial content, CommerceOS catalogue/fulfilment, and SkillForge quality review.
- Preserved the original 15 `TASK_SKILLS` canonical department baseline by putting these extra advisory routes in `PORTFOLIO_TASK_SKILLS`; no new orchestration, queue owner or dispatch authority.
- Current source inventory is **33 local skills**; 16 unique skills were selected for the new routes and all files exist locally. All 16 remain subject to manual review. Third-party scripts are not executed.
- The existing Astra `runtime/astra/department_dispatch_latest.json` snapshot contains **8 work items**. All eight already resolve to department skill recommendations; the new portfolio component names are ready for matching future owner work items, not retroactively inserted into the queue.
- `config/skill_trust_registry.json` currently has **zero approved skills**. Every new route resolves to candidates, and runtime skill-context loading still returns zero approved bodies. No false live activation claimed.
- **79 targeted regression tests passed**, covering portfolio routing, trust gates, existing SkillForge completion, promotion contracts and PDF intake. **36 additional tests passed** for SkillForge/domain checks and department work queue. Python compile checks passed.
- The real SkillForge completion reader reports **8/8 engineering checks PASS**, **16 Empire-authored skills catalogued**, **0 approved skills**, `production_changes_performed=false`, and `execution_authority=none`. `git diff --check` passed.
- A hash-indexed, **unapproved** review manifest has been recorded at `docs/handoffs/EMPIRE_ENTERPRISE_SKILL_CANDIDATES_20261119.json`. It is not a trust registry or execution permission.

## Next bounded checks before a live workflow claim

1. Confirm pre-existing knowledge intake and PDF source owner contract; map exact reader outputs to page evidence without creating a second storage owner.
2. Audit existing department task selector and add only approved exact mappings, not broad fuzzy selection.
3. Run one real per-department test on sales, engineering/design, search/data, finance and content; compare with pre-existing baseline.
4. Promote only after security review, rights checks, Founder control gates and live readback. No automatic send/spend/publish/deploy.

## 20 November 2026 — real-work-item isolated trust evaluation

- Read-only security/rights review implemented at `scripts/review_enterprise_skill_candidates_20261120.py` and tested by `tests/test_enterprise_skill_security_preview_20261120.py`. Full evidence: `docs/handoffs/EMPIRE_ENTERPRISE_SKILL_SECURITY_REVIEW_20261120.json`.
- Exactly **16** selected candidates audited. **8 unchanged internal Empire-authored skills** eligible for isolated in-memory trust loading (no production pins): `empire-evidence-verification`, `empire-fulfilment-verification`, `empire-identity-resolution`, `empire-lead-research`, `empire-product-catalog-verification`, `empire-revenue-reconciliation`, `empire-seo-intelligence`, `empire-skill-authoring`. Each has an exact SHA256 in the JSON review.
- The remaining **8** are held: `empire-engineering-verification` is modified by concurrent work; `empire-scientific-evidence-diligence` is untracked; bundled `pdf`/`xlsx` licences refer to Anthropic service agreements; `doc-coauthoring` lacks a local licence declaration; `frontend-design`, `webapp-testing` and `skill-creator` contain Apache 2.0 licence files but require independent security, suitability and legal review before any live skill pin.
- Existing department snapshot: 8 historical work items read, **5 total bounded skill context loads** in an isolated in-memory registry preview, *no live agent executions*. New portfolio workflow selectors: 8 checked. All in-memory contexts returned `execution_authority=none` and `scripts_executed=false`.
- **102 scoped tests passed** on EmpireOS; no changes to canonical trust registry (`config/skill_trust_registry.json` still has zero pins), work queue, services, database, outbound or payments.
- The SkillForge contract requires *independently labelled holdout evaluation, tenant/privacy/prompt-injection assessment, licence/ownership clearance and founder approval of each exact digest*. Automated static review and these isolated tests do not satisfy those external sign-off gates.
- This is **reviewed and tested in isolation**, **not production-approved, deployed or commercially verified**. Shared checkout is dirty; do not commit unrelated owners' changes or deploy from this tree without reconciliation.

## 20 November — deduplicated source integrity follow-up

The acceptance evaluation now includes source-hash replay, request-shape deduplication and the original SkillForge promotion preflight. Updated **64** source-record snapshots replayed with **64/64 matching hashes**, split 56 with result evidence/no queue error and 8 negative-status records lacking result evidence. Repeated work is explicitly not counted as unique independent outcomes. All eight preflight promotion attempts returned **BLOCKED**, no change to canonical trust registry. New targeted tests **57 PASS**. See `docs/handoffs/EMPIRE_ENTERPRISE_SKILL_ACTIVATION_DECISION_20261120.md` and `docs/handoffs/EMPIRE_ENTERPRISE_SKILL_SECURITY_REVIEW_20261120.json` for the final source-of-truth classification.
