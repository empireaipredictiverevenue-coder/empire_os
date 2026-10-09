# EmpireOS Evidence-Establishment Quality Contract — 9 October 2026

Purpose: upgrade the existing Search Fabric → Hunter → Buyer Probe → Deferred Enrichment → Buyer Review → ACP/GTM chain. No new timer, new agent, paid service, database migration or outbound privilege.

## Evidence states
1. DISCOVERED: a query/sitemap suggests a page, not proof.
2. OBSERVED: a specific page was retrieved within crawl budget.
3. COMPANY_CORROBORATED: known company is genuinely associated with source.
4. PERSON_CORROBORATED: named person, current role and company fit established.
5. CONTACT_BOUND: exact published person-email linked to the established company.
6. BUYER_DEMAND_VERIFIED: evidence that this actual entity buys the target product; marketplace, broker and publisher classifications are separate.
7. REVIEW_ELIGIBLE: all prior checks pass; founder, history, suppression and outbound gates remain independent.

## Implemented safety rules
- First-party URL, known company domain and published email must align on the same exact host (allowing only www normalisation).
- A domain alias, franchise parent, marketing provider or similar shared suffix does not imply common ownership. Conflicts go to manual identity review.
- Direct publication must be explicitly observed, not inferred from email patterns or MX/SMTP acceptance.
- Directory evidence must come from an established directory host and government evidence from a genuine government host. Secondary claims require corroborated business identity and named role.
- Rejection reasons are recorded by category. No first-party claim can self-certify when the known company website is missing.
- All automated commercial authority gates stay unchanged.

## Research-backed next phases — not implemented yet
1. Claim-level provenance receipts: source URL, candidate and person IDs, normalized claim type, observation time, content hash, supporting excerpt, collection activity and reviewer decision. Based on W3C PROV concepts of derivation, generation and attribution.
2. Change-aware evidence validity: conditional retrieval using ETag and Last-Modified, per-claim freshness deadlines, conflicting page versions, and explicit invalidation. HTTP 403/429 or search failure must not be interpreted as negative buyer evidence.
3. Separate classification of direct lead/call buyers, affiliate brokers, publishers, technology platforms and unknown companies. Require direct purchasing evidence before claiming buyer demand.
4. Bounded first-party sitemap discovery and robots-aware crawling; prioritise relevant pages rather than increasing unlimited search volume.
5. Trust and reliability scoreboard: qualified reviews per 100 candidates, percent with exact person-email proof, source rejection reasons, conflicting-identity rate, recheck latency, network failures and handoff completion.
6. Review-required domain-alias and identity dispute queue; never automatically bypass suppression or founder approvals.

## Acceptance gates
- Tests proving spoofed URLs, shared-suffix lookalikes, incorrect directory or government labels, absent explicit publication and missing company identity are rejected.
- Full regression Buyer Probe → Deferred Enrichment → Buyer Review → ACP/GTM → Outbound Governor.
- Observe-only real company-site sample measuring source-confirmed review yield. Green unit tests are not commercial outcome proof.

References:
- W3C PROV-O https://www.w3.org/TR/prov-o/
- Google ProfilePage https://developers.google.com/search/docs/appearance/structured-data/profile-page
- Public Suffix List https://publicsuffix.org/
- IETF RFC 9309 https://www.rfc-editor.org/rfc/rfc9309
- Companies House API https://developer.company-information.service.gov.uk/get-started

Companies House API requires credentials; an officer record does not itself prove email ownership or product buying intent.
