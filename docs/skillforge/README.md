# Empire SkillForge — Sovereign Agent Skills & Learning

**Engineering closeout:** See [COMPLETION.md](COMPLETION.md) for the one-command acceptance gauntlet, verified coverage and exact founder/evidence gates.

**State:** OBSERVE. Evidence-backed learning observations and private review drafts are created by the existing department worker; skills are **not automatically approved or executed**.

## The actual connected flow

Astra approved/eligible department plan → existing durable department queue → existing governed worker → canonical work DONE with result evidence → one private, deduplicated SkillForge observation → validated learning index → checkpoint-based immutable draft → evaluation/review → separately approved and SHA-256 pinned skill → bounded loader for authorized agent contexts.

No separate timers or third-party runtime. Existing production authority gates for suppression, outbound, spending, fulfilment, payment, tenant isolation, migrations and revenue remain unchanged.

### Current structures

- `empire_os/skills_library/skills/empire-*/SKILL.md` — Empire-owned skill pack candidates (11 packs initially). Existing third-party skills elsewhere in the legacy library are **not** automatically discovered by SkillForge task routing.
- `config/skill_trust_registry.json` — manually governed digest-pinned approvals. An empty `approved_skills` map means no skills can be loaded.
- `empire_os/skill_exchange.py` — explicit exact component/department/task mapping. Observed Astra department keys are mapped rather than guessed from prose.
- `empire_os/skill_trust.py` — rejects missing or changed approvals, escaped paths and oversized context. Agent skill context is capped to prevent unbounded prompt injection.
- `runtime/skillforge/observations/skill_observation_*.json` — private (0600) canonical-completion observations with hashed work IDs, result and evidence references; no raw result bodies are copied.
- `runtime/skillforge/proposals/skill_proposal_*/{manifest.json,SKILL.md}` — private (0600), review-only drafts generated after 3, 5, 10, 20, 50, 100... distinct evidence-validated work completions for a component/adapter. The template states what must be validated; it **does not** claim a successful generalizable procedure has been learned.
- `empire_os/skillforge_proposals.py` — revalidates observations against canonical DONE records before proposing. Corrupted or unverified observations block writes. A recorded draft never inherits approval when content changes.

### Observable production proof

On 9 October 2026, the running `/srv/empire_os` checkout contained multiple SkillForge observations whose work IDs, component, adapter, result digest and evidence links matched canonical DONE queue records. Two review draft versions were created from commercial product catalogue and Predictive Cloud opportunity-loop observations. This is **runtime learning capture**, not evidence that agent task quality or actual sales increased.

## Operator commands

```bash
cd /srv/empire_os
./.venv/bin/python scripts/skillforge_catalogue.py
./.venv/bin/python scripts/skillforge_evaluate.py
./.venv/bin/python scripts/skillforge_refresh_proposals.py
./.venv/bin/python scripts/inspect_department_skill_context.py --department market_intelligence --component predictive_cloud_opportunity_loop
```

The refresh command above defaults to **dry-run**. To save only internal unapproved review drafts in the private runtime directory, use `./.venv/bin/python scripts/skillforge_refresh_proposals.py --apply`. No production service restart or extra timer is required for draft capture through the existing worker path.

Preflight exits nonzero until explicit skills are approved. Static evaluation checks only a basic local instruction contract; passing it is not permission to use the instructions and does not measure task quality.

## Review/promotion conditions

1. Examine the actual canonical evidence and compare successful outcomes to a baseline rather than inferring quality from `DONE` state, counts, estimates or optimistic forecasts.
2. Verify a generalizable procedure using independent holdout tasks, failure cases and measurable outcomes.
3. Check owner/licence provenance, customer data boundaries, tenant identity, prompt injection and tool permissions.
4. Author a new bounded, independently verified skill and tests. A review draft is not an approved library item.
5. Record explicit approval and a matching SHA-256 of the exact authorized skill text; a change requires review and reapproval.
6. Load only approved skills with the bounded loader; no skill can grant additional execution or commercial authority.

**Known gaps:** SkillForge does not yet automatically run independent quality evaluations, infer genuinely superior procedures, or promote proposed skills; legacy agent modules may still use their older third-party skills loader and need a separate audit before consolidation. Hashes are pseudonymous identifiers, not proof of anonymization or independent cryptographic attestation. Do not copy confidential information into a proposed skill.

## Stage 2 — offline quality evaluation and controlled promotion

SkillForge V2 adds three distinct review instruments. None can grant commercial authority or trust by itself:

- `scripts/skillforge_benchmark.py --suite /path/to/holdout.json` scores paired baseline/candidate **already-produced** decision JSON against supplied expected labels. It requires the v1 suite schema, evidence-hash identifiers, bounded unique holdout cases, negative cases, and prohibits claims that live outbound/payments/writes occurred. It reports exact-match accuracy, wins/regressions, negative-case failures and a strict **numeric-only** gate. The labels and evidence hashes are *supplied assertions*, not independently authenticated; the report always says independent quality is unverified.
- `scripts/skillforge_promotion_preflight.py --skill-name empire-reply-triage [--suite /path/to/holdout.json]` binds the evaluated result to the **exact skill content digest**, then lists outstanding independent evaluation, reproducibility, licence, privacy, prompt-injection and founder approvals. It never edits `config/skill_trust_registry.json` and never claims a skill promoted.
- `scripts/skillforge_local_smoke.py` optionally tests a candidate's influence on the local model at the **fixed loopback URL** `127.0.0.1:11435` using two built-in synthetic examples. No agent tools, DB, emails, payments, browser, external inference provider, or real customer data are available. This is a wiring smoke test only (2 cases), not a verified holdout benchmark. Outputs include no raw source examples and cannot qualify for promotion.

The review sequence for a real skill is: collect independent case labels with provenance → run bounded agent evaluation on an isolated model/workspace → compare baseline and candidate accuracy including negative cases → validate evidence and outcomes against source truth → confirm stable operational behaviour and licensing/tenant safety → explicit founder approval for the exact digest → reviewed source-controlled update of the trust registry. A manually set `status=approved` is not cryptographic proof of founder intent; authoritative code review and deployment gates must remain separate.

## Stage 2 — legacy loader consolidation

The old `empire_os.skills_library` API now returns only approved, digest-pinned Empire-owned `SKILL.md` content. Unknown roles and unapproved, changed, missing, escaped or overlong skills return no instructions. No Anthropic brand/presentation/document pack is automatically injected.

`SyntheticAgent` no longer loads its historic unreviewed `skills.jsonl` entries as prompt skills, nor reads arbitrary third-party `SKILL.md` files as persona SOULs. Historic success notes remain *untrusted activity data*; these are not automatically translated into verified reusable procedures.

The Empire Coder Knowledge Garden still records candidate knowledge status, but ACTIVE/task promotion alone is **not** SkillForge instruction approval. `ContextBuilder` will not inject arbitrary library skill excerpts into context. The explicit Coder `SkillLoader` requires both ACTIVE knowledge state and a matching Empire SkillForge trust digest; only complete, bounded instructions may be retrieved.

The legacy email expert no longer reads `/tmp/repo_skills`; it drafts from the approved Empire commercial email pack if/when one is reviewed. Its remote compliance-check outage fallback is fail-closed. Neither the email skill nor this change gives outbound send authority.

**Remaining scoped work:** coder graph still contains legacy skill names as selection metadata (they cannot load through the guarded path); some specialized agents operate dedicated open-source research engines separately from skills (for example the last30days engine). Those are separate integrations requiring their own execution, licence and data boundary audit. No third-party repo or skill library was deleted or silently approved.
