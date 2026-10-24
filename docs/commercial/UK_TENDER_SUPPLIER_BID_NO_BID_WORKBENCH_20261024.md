# EmpireOS — official UK tender bid/no-bid evidence workbench
24 October 2026 | Original EmpireOS / EmpireDB | controlled research release

## Exact production evidence
The original `empire_os.acquisition_official_tender_intake` fetched Cabinet Office OCDS release packages from Contracts Finder and Find a Tender at 2026-10-24 09:42:46 UTC, refreshing the original permissioned private receipt. Six open service requirements survived its bounded metadata classification out of 278 inspected releases. This is NOT an exhaustive UK tender search.

The previously installed deadline review is `DEADLINES_TRIAGED_REVIEW_ONLY`. The newly added `scripts/review_official_tender_bid_no_bid_20261024.py` reads the same private authoritative receipt via the existing restricted triage validator. A public procurement notice proves that a purchasing requirement was published; it does not prove Empire AI is eligible, technically qualified, permitted to bid, has the necessary staff/certifications, or will be paid.

### Current decision register (no company contact or bid)
| Deadline UTC | Notice | Decision | Missing proof |
| --- | --- | --- | --- |
| 26 Oct 12:00 | GDPR Data Audit | HOLD_SUPPLIER_COMPETENCE_AND_DELIVERY_SCOPE | Latest full issuer docs; independence, legal/privacy audit expertise and evidence; contract scope, duration, insurance and delivery capacity |
| 30 Oct 12:00 | Dublin–Belfast Economic Corridor Investment Land Guide | HOLD_SUPPLIER_COMPETENCE_AND_DELIVERY_SCOPE | Full issuer spec and clarifications; geography/land economics/GIS expertise if needed; rights, reference projects, deadlines and deliverable fit |
| 4 Nov 12:00 | Northampton College Media Planning & Buying | NO_BID_OR_RESTRICTED_SCOPE_PENDING_ORIGINAL_POLICY_OWNER | Paid traffic conflicts with original no-paid-traffic policy |
| 10 Nov 12:00 | Tourism Campaign – Digital Marketing | NO_BID_OR_RESTRICTED_SCOPE_PENDING_ORIGINAL_POLICY_OWNER | Paid scope independently excluded? Not currently proven |
| 11 Nov 12:00 | Digital Media Planning and Buying | NO_BID_OR_RESTRICTED_SCOPE_PENDING_ORIGINAL_POLICY_OWNER | No-paid-traffic policy hold |
| 13 Nov 17:00 | Tourism Campaign – Digital Marketing | NO_BID_OR_RESTRICTED_SCOPE_PENDING_ORIGINAL_POLICY_OWNER | Paid scope independently excluded? Not currently proven |

The date, title and policy classifications above are values observed in the original official feed, not a direct document/amendment confirmation or licence to bid. Supplier required credentials are UNKNOWN until the original tender documents have been reviewed; examples given are assessment questions, not a declaration that such qualifications are required for every notice.

## New owner's exact private CLI
```bash
cd /srv/empire_os
.venv/bin/python -B -m scripts.review_official_tender_bid_no_bid_20261024 --repo-root /srv/empire_os --write-private
```

Result: `RESEARCH_ONLY_BID_NO_BID_TRIAGED` or fail-closed `HELD_OFFICIAL_TENDER_RECEIPT_UNVERIFIED`. The atomic 0600 output resides solely in `runtime/acquisition_research/official_tender_bid_no_bid_latest.json` under the original 0700 private research folder. It does not schedule a new worker, modify the database, claim a buyer, send a letter, submit any bid, procure credentials, approve legal terms, move money, or alter systemd. A source snapshot older than 24 hours must be refreshed through the existing original official read-only intake before a new decision.

## Independent supplier and economic gates
For any held or proposed opportunity, original owners must independently verify *each*:
1. Official notice identity, latest amendment, current deadline, procurement portal submission conditions and complete lots/attachments.
2. Legal supplier eligibility, conflict of interest, residency/geographical limits, past performance and mandatory insurance/certification requirements. Do not assume a sole trader qualifies or has credentials that have not been verified.
3. Exact scope of services, milestones, buyer acceptance and security/privacy obligations, right to use sourced data and subcontracting terms.
4. Capacity: who performs each specialist task, schedule, loaded labour hours/rates and evidence of delivery experience.
5. Cost components: labour, subcontractors, licensing/data/software, compliance/insurance, travel, overhead and contingency. All sourced and checked, with genuine proposed price excluding VAT and appropriate tax review. Financials may be simulated internally but are NOT bid pricing or proven margin.
6. Independent founder decision and actual sign-off of bid, price, contract terms, supplier declarations and approved delivery route. Reconciliation to original company CRM and payment provider only after authentic accepted commercial evidence.

The included `hypothetical_margin()` is a pure, tested internal cash contribution formula: labour + direct costs + overhead + contingency; contribution = net price - cost; contribution percentage = contribution / price. Its input is *not* used by the live tender register until real owner evidence exists, and its output is explicitly `HYPOTHETICAL_UNAPPROVED_SCENARIO_ONLY`. It excludes VAT and tax and never authorises bids or revenue recognition.

## Verified production result
- 6 notices assessed; 2 supplier-and-custom-scope holds; 4 paid-policy / unclear scope no-bid holds.
- 0 bid-ready; 0 qualified Empire AI customers; 0 verified actual project economics; 0 supplier eligibility confirmations; 0 revenue.
- No emails, bids, CRM writes, payment activation, automation or governor activation.
- Existing outbound governor remains inactive.
- Next action for the original tender owner: independently review the 26 Oct GDPR tender’s actual attachments and supplier specifications first; if specialist capabilities and evidence cannot be assembled before the closing deadline, mark NO-BID instead of inventing qualifications.

## Latest official issuer-document inventory — 24 October 2026
The existing original official Contracts Finder OCDS GET pipeline was re-queried. Its Cabinet Office bulk release packages directly expose the latest Ryde Town Council GDPR amendment (21 October) and original 7 October release, plus the Dublin–Belfast Investment Land Guide 14 October notice. This is the source metadata of the official issuer and cannot substitute for the contents of a PDF, DOCX or locked supplier portal.

A separate per-notice OCDS record endpoint responded HTTP 404 and original document attachment GETs returned HTTP 403 from the authorised public check. The owner MUST NOT bypass those restrictions, claim attachment inspection or act as an eligible supplier based on inferred conditions.

The new `scripts/review_official_tender_issuer_documents_20261024.py` runs in read-only research mode with the existing bounded official OCDS source and latest 24-hour original private deadline triage. It retrieves only public release metadata, does NOT download individual attachment files, and records their exact issuer URLs, types, dates/versions and mandatory missing-document flags.

Live receipt: `ORIGINAL_ISSUER_DOCUMENT_REFERENCES_OBSERVED_NOT_VERIFIED`, 2 original notices, 9 current document references, 1 amendment record observed. Ryde's 8 current references comprise 1 tender notice, 3 bidding-document references, 2 clarification references, and 2 technical specification references (sample output and staff structure). The corridor land guide has only its notice URL in the official release and refers suppliers to the MultiQuote portal for the competition documents. Any price ceiling, estimated contract value, exact delivery requirement, accreditation or expected costs remain UNVERIFIED by this document-inventory check.

The private mode-0600 manifest is `runtime/acquisition_research/official_tender_issuer_document_index_latest.json` in original mode-0700 research folder. No new timers, attachments copied, third-party logins, customer records, bid submissions or financial actions.

Next original procurement owner step: obtain legitimate access to each issuer document through normal supplier channels, review contents and clarification changes, then establish qualification, legal obligations, delivery cost and final date. Without that evidence by the closing deadline, label NO-BID.

## 24 October — PRIMARY COUNCIL PDF AND DOCX DOCUMENTS VERIFIED

The former Contracts Finder attachment endpoint returned HTTP 403, but Ryde Town Council independently publishes the tender's original documents at its official `https://rydetowncouncil.gov.uk/transparency/` page. No bypass of the Contracts Finder attachment controls was attempted. The four independently issuer-published files were directly retrieved over HTTPS, byte-checked, pinned to reviewed SHA-256 digests, and the request-to-quote PDF and supplier due-diligence PDF were read/visually checked. The two DOCX supplier forms were parsed to verify they are the expected pricing and references templates. This does NOT mean the original Contracts Finder attachment set was downloaded or that all follow-up clarifications have been reviewed.

**Exact original publisher sources, owner inspection scope:**
- https://rydetowncouncil.gov.uk/wp-content/uploads/2026/10/Request-to-Quote-Data-Audit-1.pdf
- https://rydetowncouncil.gov.uk/wp-content/uploads/2026/10/Due-Dilligence-Check-Sheet-Summary-1.pdf
- https://rydetowncouncil.gov.uk/wp-content/uploads/2026/10/Pricing-Shedule-Data-Audit-1.docx
- https://rydetowncouncil.gov.uk/wp-content/uploads/2026/10/References-1.docx

**Genuine issuer deadline conflict:**
- Contracts Finder OCDS bulk release metadata reports `2026-10-26T12:00:00Z` as the procurement tender end date.
- Council Request to Quote PDF schedule says 26 October 2026 is the deadline for *clarification questions*, while **2 November 2026 at noon** is the deadline for *quotation submission*, repeated again on the final PDF page.
- This discrepancy MUST remain open until the issuer explicitly confirms which deadline governs. Never silently change an original release field or assert that the bid is open until 2 November.

**Actual mandatory specialist requirements in original Request to Quote (not inferred):**
- Named auditors with recognised data-protection qualification such as BCS Practitioner Certificate, PC.dp, CIPP/E or equivalent; demonstrable comparable local authority/public-sector audits.
- Professional indemnity insurance **at least £5,000,000** and public liability insurance **at least £5,000,000**.
- ICO registration as a data controller, own documented privacy/security arrangements, declaration of independence and conflicts, and **two references for comparable work within three years**.
- At least some fieldwork **on site** at the council in Ryde, including interviews, document review and systems/working-practices observation.
- Deliverables include inception plan, draft evidence-backed RAG audit report, prioritised action plan, Article 30 ROPA, information asset register and data-flow map, final plain-English audit report, and presentation to councillors. Edited electronic copies belong to Ryde Town Council.
- Work covers UK GDPR, Data Protection Act 2018, Data (Use and Access) Act 2025, PECR, ICO guidance and relevant information governance.
- Separate due-diligence form asks for supplier identity, relevant accounts/tax-return evidence, insurance certificates and health/safety declarations. The references DOCX asks for organisation details, completion dates and contract values.
- The council's **pricing schedule is an unfilled supplier template**, NOT confirmation of a £0 contract or a verified project value.
- The *stated* bank-transfer payment milestones are **20% on appointment, 20% before fieldwork, 30% on draft report, 30% on final report and presentation**. This is procurement text, NOT accepted payment terms, invoicing or money received.

**Original EmpireOS integration:** `scripts/reconcile_ryde_original_issuer_documents_20261024.py` downloads only the four exact allowlisted public files with no redirects, hashes, size/MIME/format checks, and fails closed on changed content. It atomically stores a mode-0600 review receipt under the existing mode-0700 private tender runtime at `runtime/acquisition_research/ryde_gdpr_issuer_requirements_latest.json`. The existing original `scripts/review_official_tender_bid_no_bid_20261024.py` joins the restricted receipt *only if* matching original OCID, notice, old source deadline, four pinned hashes and a fresh timestamp pass validation. It shows both deadlines and all hard supplier gates, while retaining original tender closure metadata and no-bid authority. It does not send clarification email, submit quotes, fill forms, grant access, activate payment or operate the CRM. No database writes or new timers/services.

**Decision until owner's evidence:** `HOLD_SUPPLIER_COMPETENCE_AND_DELIVERY_SCOPE` (not supplier eligible). No named data-protection auditor qualification, comparable public-sector audit experience, £5m certificates, ICO registration, independent audit status, legal contractual capacity, onsite availability or contract cost basis has been independently proven *for Empire AI*. Any absent mandatory item means NO-BID unless demonstrably remedied before the actual issuer-confirmed submission deadline. A speculative intermediary partnership or guessed subcontractor does not establish compliance. Ryde is unsuitable for an unsupervised software-only delivery.

**Revenue discipline:** Tender research, a completed pricing template, an optional quote draft and an authority's published payment schedule are none of: accepted offer, signed contract, performed deliverable, invoice settled or recognised revenue. Continue the same original EmpireOS and one EmpireDB.
