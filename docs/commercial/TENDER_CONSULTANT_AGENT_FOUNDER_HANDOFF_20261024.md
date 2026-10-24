# EmpireOS Tender Consultant Agent — native on-demand specialist
24 October 2026 | Existing EmpireOS / original EmpireDB | read-only founder review

## Why built
The user's instruction was to develop a consultant agent to work the **original tender intelligence programme**, specifically the live 2026 Ryde GDPR audit and £25,000 Dublin–Belfast Investment Land Guide. This is the consultant/research capability of Empire AI, *not* a newly formed agency, second CRM, independent contractor, accredited auditor, automated bidder or promised win.

## Existing control fabric and code
- Registered one observe-only `tender_consultant` specialist in the canonical `empire_os/agent_execution_plane.py` registry. Capability `tender_bid_consultation`. Requests for external authority / internal-write routing are denied. On-demand routing happens with the pre-existing `ExecutionJob` and `route_execution_job` functions.
- Consultant analysis in `empire_os/tender_consultant_agent.py`; private command entrypoint `scripts/run_tender_consultant_agent_20261024.py`. All source access is limited to existing private, chmod 0600, 24-hour bounded `runtime/acquisition_research/official_tender_bid_no_bid_latest.json`. Provenance comes through the original official procurement intake, official issuer document proofs and independent public notice reconciliation. No additional website scraper, API key, seller portal or new infrastructure.
- No additional systemd service/timer, container, background process, paid API, agency, database migration, CRM write or externally executable workflow was installed.
- The routing field `reports_to: CHIEF_OF_STAFF_FOUNDER_REVIEW` marks the correct review owner but **does not itself submit a real Chief of Staff queue task**. The original CoS must approve any future scheduling/dispatch integration.

## Actual consultant deliverables
Command (read-only preparation + *explicitly optional* private local output):
```bash
cd /srv/empire_os
.venv/bin/python -B -m scripts.run_tender_consultant_agent_20261024 \
  --repo-root /srv/empire_os --write-private
```

Private mode-0600 output: `runtime/acquisition_research/tender_consultant_founder_brief_latest.json`, within original mode-0700 research directory.

One private consultation contains two strictly evidence-scoped dossiers and **11 owner tasks**. It does not claim to have assigned those tasks to real people or contacted them.

### Ryde GDPR audit: NO BID unless all specialist proof exists
Original council's published request-to-quote shows:
- Named independent professional auditor with BCS Practitioner, PC.dp, CIPP/E or equivalent expertise, completed comparative public authority engagements.
- £5m professional indemnity and £5m public liability insurance, ICO registration, independence, cybersecurity/data-handling, two references, and at least some in-person fieldwork in Ryde.
- Legal/privacy review, council-facing report and action plans, and required data mapping evidence.
- Original public PDF and government aggregate feed still disagree: issuer PDF shows 2 Nov 2026 noon as quote deadline, government aggregate 26 Oct noon as tender close, PDF 26 Oct as clarification cut-off.

Five original-owner tasks: confirm actual date and amendment, qualify the named legal/data-protection professional, verify real certificates and references, resource on-site specialist delivery, and calculate full verified costs only after eligibility. The AI cannot certify or conduct a formally independent professional audit on its own.

### CA18567: Hold until RFQ and real land-investment consultant verified
Two independent original public government notices show:
- Newry, Mourne and Down District Council/DBEC; public **£25,000 estimate** only; SME suitability yes.
- **80% quality, 20% price**. Actual scoring questions and detailed supplier requirements are behind MultiQuote's CA18567 RFQ. No invented bid criterion, design brief or claimed pass mark.
- 26 Oct questions deadline, 30 Oct full-notice noon submission; government summary displays 31 Oct, still an unresolved portal cutoff inconsistency.
- Planned supplier work period from 30 Nov 2026 to 31 Mar 2027.

Six original-owner tasks: legitimate full MultiQuote RFQ and cutoff verification; independent land/economic/GIS specialist qualifications and previous work; planning, site, data/ownership rights; genuine deliverable work-breakdown; independent labour, licence/design/travel/compliance costs; then founder bid/no-bid and price terms approval. The agent's guide outline is a **hypothesis for discussion**, not an accepted customer specification.

## Optional local AI shadow
```bash
.venv/bin/python -B -m scripts.run_tender_consultant_agent_20261024 \
  --repo-root /srv/empire_os --write-private --shadow-local
```
This uses only the existing loopback model `qwen2.5-coder:1.5b`; it sends a fixed, publicly supported summary to localhost, NEVER original secure source bodies, buyer contacts, secrets or tender credentials. It asks for four candidate due-diligence questions. Output must follow a strict short question-only shape and remains `LOCAL_SHADOW_QUESTIONS_UNVERIFIED_FOR_HUMAN_REVIEW`, separately from official facts. The **first live local model call was held** (`SHADOW_ADVICE_HELD_NO_NEW_CLAIMS`) because output failed validation, so no AI-generated questions were accepted. It does not affect the successful deterministic consultant plan. No external inference subscription or remote processing.

## Operating and commercial truth
The live initial run: `CONSULTANT_BRIEF_PREPARED_REVIEW_ONLY`, 2 briefs, 11 proposed owner actions, 4 policy-held other procurement notices, **zero** bid-ready, zero verified supplier credentials, zero accepted quotes, zero customers, zero bids, zero CRM writes, zero sends, zero portal logins, zero payment actions or recognised revenue. All source document links and 80/20 split remain evidence for strategic discussion, not proof of qualification or a sale.

This capability is an internal decision-support agent. To become a bidder it would require independent evidence of an eligible actual legal supplier, properly qualified consultant(s), legitimate portal and tender-document access, dated staffing references, a sourced cost/margin basis, independent terms review and fresh explicit founder authority through the original procurement and security governors. Never grant that authority through model output.

## Next original tender build
Attach legitimate supplier RFQ content after original owner access, verify detailed criteria and special conditions with human consultant, map evidence-backed project staffing and site research resources, and generate a quote draft for explicit founder review **only after** verified costs and scope. Integrate source-reviewed consultant plans to Chief of Staff's existing internal review queue only after confirming the original queue schema and approval. Do not register new schedulers or contact buyers from a research task.

## 24 October — guarded CA18567 supplier-RFQ documentary intake (no portal access)

The founder executed the original native consultant entrypoint successfully on 24 October at 13:26:14 UTC: `CONSULTANT_BRIEF_PREPARED_REVIEW_ONLY`, two original public tenders, 11 proposed owner-review actions, zero bids/customers/contracts/CRM writes, and no outbound. The founder's run is accurate; no unsupported supplier validation should be inferred from it.

The next source dependency is real: the **full original CA18567 RFQ is not yet available** in EmpireOS. Public government notices establish the £25,000 estimated contract budget, 80% quality / 20% price overall weighting, the 26 October clarification cutoff and the full-notice 30 October submission deadline (public summary anomalously says 31 October), but the actual detailed scoring questions, contract conditions, supply criteria and legal rights are behind the original MultiQuote supplier portal. No portal authentication, account registration, private file acquisition or binding acceptance was performed.

**Original private intake created:**
`/srv/empire_os/runtime/acquisition_research/tender_supplier_documents/CA18567/` — mode **0700**, existing EmpireOS research tree only. No source documents are present yet.

**Source-custody commands (optional, authorised private research):**
```bash
cd /srv/empire_os
.venv/bin/python -B -m scripts.prepare_tender_supplier_evidence_intake_20261024 \
  --repo-root /srv/empire_os --prepare-private-drop --write-private
.venv/bin/python -B -m scripts.run_tender_consultant_agent_20261024 \
  --repo-root /srv/empire_os --write-private
```

Output mode **0600**: `runtime/acquisition_research/land_guide_supplier_documents_inventory_latest.json`. Current live status: `AWAIT_AUTHORISED_MULTIQUOTE_RFQ_FILES`, 0 files, issuer-provenance `NOT_AUTHENTICATED_BY_ISSUER`.

Original owner ONLY, once explicitly and lawfully downloaded from the real MultiQuote opportunity, can place allowed `PDF`/`DOCX` supplier files in the private drop (file mode 0600, original directory mode 0700). The fixed allowlist accepts up to eight simple-named files, up to 12 MB each / 28 MB total. The code rejects symlinks, hardlinks, wrong magic, malformed archives, unexpected permissions, future timestamps and unbounded decompression metadata. No uploaded file instructions are executed; files are never sent to an LLM or external API. A received hash is evidence of *local file custody only*, not document publisher authentication, human review, professional qualification, current amendment status or permission to subcontract.

The consultant's original Founder receipt now carries `ca18567_supplier_document_intake`. It reports `AWAIT_AUTHORISED_MULTIQUOTE_RFQ_FILES`, `SUPPLIER_FILES_OBSERVED_NOT_AUTHENTICATED_OR_REVIEWED` or a strict `HELD` for unsafe files. **All states** retain `full_rfq_reviewed=false`, `scored_quality_criteria_verified=false`, `supplier_eligibility_verified=false`, `bid_authorized=false`. A subsequent qualified human consultant must review the original RFQ and provenance against the lawful publisher portal before any commercial gate can be considered.

No other tenant, external sales agent, production cron, file library, database schema, outbound governor, messaging service, legal declarations, payments or bid submissions were modified. The restricted original on-demand specialist remains under `tender_consultant` in the existing `agent_execution_plane`.

**Next milestone:** acquire actual RFQ documents by authorised human supplier access, inspect the scoring breakdown and specialist land-investment requirements, source staff and GIS/data rights/cost evidence, and deliver a defensible founder bid/no-bid memo. If these cannot be proven before the real closing deadline, the original owner should decline instead of inventing eligibility.
