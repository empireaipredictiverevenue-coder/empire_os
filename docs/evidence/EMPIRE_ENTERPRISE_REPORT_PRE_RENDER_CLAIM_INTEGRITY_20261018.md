# EmpireOS — enterprise diagnostic report claim-integrity pre-render gate

**18 October 2026 | Founder data-product accuracy | no new agent, service or sender | OBSERVE**

## Exact production gap reproduced

A live read-only test on the existing EmpireOS enterprise diagnostic report builder demonstrated an internal *rendering* integrity issue. Its HTML/Markdown renderers already check the top-level "INTERNAL_DRAFT_NOT_CLIENT_DELIVERABLE" disposition, chapter count and external release false, but the Markdown renderer does not recompute the nested `completeness.findings_verified` field.

Using a **deep-copy** of a real zero-client-finding report, setting `completeness.findings_verified=42` caused the existing Markdown renderer to emit "Verified client-facing findings: 42" despite having zero verified findings. That was a manipulated **in-memory test copy** only. Neither production data nor user/customer files were changed. This is not proof customer delivery was enabled; it shows an internal analyst could be shown a false verified count if a payload were modified after assembly.

**Ownership boundary:** The actual report assembler, Markdown/HTML renderer and `predictive_revenue_demo_api.py` route files are presently untracked or locally modified work owned by another EmpireOS agent. This release does **not overwrite those files**, does not patch the other agent's worktree, and makes no claim that every existing HTML/Markdown endpoint is already intercepting this new guard.

## Implemented isolated, testable mechanism

New code `empire_os/enterprise_report_claim_guard.py` introduces:

- `validate_enterprise_report_before_render(report)`: fail-closed check of the exact existing 12-chapter enterprise report format, pseudonymous case, source-workbench identity, existing release flags, required named human-review roles, source custody/tenant/financial-review flags, and no financial writes or outbound activity.
- **Finding-level integrity:** every finding must be an explicitly unverified client-supplied investigative hypothesis. Cohort denominator/rate must recompute. No finding may assert verified causal attribution, revenue recovery, investment return or automated client authority. No duplicate finding IDs. All findings must belong to a distinct chapter, must exactly match that chapter's investigative list, and must have a pending intervention decision and no approved spend.
- **Counts and references recomputed:** `chapter_count`, per-chapter finding counts, full `completeness` inventory including unverified/verified count, source appendix relationship and source claims, pending decision register and source custody statuses are derived/validated, not trusted as submitted data.
- **Evidence claim boundary:** source references are `source:` or `canonical:` claimant identifiers, not independently verified original records. Source appendix may **not** assert the original was read, source integrity verified or tenant permission established. This guard never converts such references into a verified client finding.
- **Wrapper `guarded_enterprise_report_render(report,format)`:** deep-copies the original report, runs the complete guard and *then* calls the existing original HTML/Markdown renderer only on the same copy. Tampering such as 42 fabricated verified findings is refused before entering the renderer. The local SHA-256 identifies the checked JSON snapshot, **not** a publisher or accountant's digital signature.
- `scripts/preview_enterprise_report_evidence_readonly.py`: explicitly on-demand `--read-only --format verify` performs a bounded read from the existing report builder and validates the resulting internal draft. Optional `--format html` and `--format markdown` render through the new guard to stdout; no files, database or email writes. No source extractor is added.
- `tests/test_enterprise_report_claim_guard_20261018.py` tests 12-chapter normal form; nonzero and zero unverified findings; falsified verified count; supplied unverified "evidence" promoted as fact; cross-chapter record inconsistency; approved spend; fake reviewer signing; missing original-source references, finance or release escalation; and a renderer stub verifying no original renderer is called on manipulated input.

### On-demand founder check

```bash
cd /srv/empire_os
./.venv/bin/python -B -m scripts.preview_enterprise_report_evidence_readonly --read-only --format verify
```

This should return `INTERNAL_UNVERIFIED_DRAFT_STRUCTURE_VALIDATED` for the existing unchanged report with:
- 12 investigative chapters.
- 0 independently verified client findings (as of the 18 October 2026 test).
- `customer_delivery_authorized=false`, `underlying_finance_audited=false`, `source_reference_claim_only=true`.

That means the **internal report structure and honesty of its unverified labels** passed. It does **not** establish actual client financial truth. The full enterprise workflow still needs independently authorised CRM/finance custody, source reconciliations and a separate explicit release decision before customer delivery.

## Evidence-backed checkpoint and open integration

Observed with the actual production report builder in memory on 18 Oct:
- Original 12-chapter report: ordinary existing HTML renderer produced a printable internal draft; Markdown produced an internal investigative report.
- Altered copy `findings_verified=42`: existing Markdown renderer displayed the false 42. **This was reproduced once and reported as an internal review finding, not a live customer error.**
- The new pre-render gate accepted the original report as `INTERNAL_UNVERIFIED_DRAFT_STRUCTURE_VALIDATED`.
- The same tampered 42-count copy was **denied** with `ENTERPRISE_REPORT_EVIDENCE_HOLD:FINDING_COMPLETENESS_FORGED` before HTML rendering.

**Next needed owner integration:** The agent owning `empire_os/predictive_revenue_demo_api.py` should use the checked wrapper for `/product-workbench/enterprise-report/preview` and `.../markdown`, and run `validate_enterprise_report_before_render(report)` before returning the raw JSON endpoint. That is a **separate selective merge/integration** into its ongoing uncommitted work. Do not overwrite or reset that worktree. Actual public/tenant route visibility, authentication and customer entitlements must be checked separately. This release explicitly does **not** claim all three live endpoints are now protected by the new adapter.

All three unchanged report paths already use a founder-oriented existing router and leave delivery gates OFF. This project adds no new database, entity/tenant migration, scheduler, source API, paid model, outbound email, commercial approval or source revenue recognition.

**Evidence rule:** an investigator's unverified hypothesis must never be presented as a verified economic finding. Any source reference can support investigating a hypothesis; supporting a real statement requires exact source custody, identity, timing and reviewed authority, and permitting customer delivery requires separate approval.
