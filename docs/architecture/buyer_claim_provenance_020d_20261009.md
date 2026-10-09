# Buyer Claim Provenance — 020D

## Purpose
Close the evidence-establishment gap across both Buyer Scout discovery paths,
holding-area persistence, Buyer Review, ACP and governed promotion.
This extends the existing EmpireOS evidence architecture, not a new agent.

## Observed evidence contract
The first-party Scout receives fetched pages from Search Fabric. For each
same-domain page (maximum five), the detector retains:
- first-party source URL; validated company domain
- observed-at ISO8601 time in UTC
- SHA-256 of the page's **captured visible text** (not an external attestation)
- exact supporting sentence excerpt (up to 220 characters)
- deterministic relationship classification and evidence state

A claim receipt means a first-party site published a statement, not that the
company purchased actual inventory or has confirmed budget or commercial terms.

Buyer relationships: direct inventory buyer; intermediary/marketplace;
lead supplier/publisher; mixed-role requires review; unknown.

Direct purchasing requires a clear first-person buying statement on a fetched,
same-company page, with no corroborated supplier/intermediary role conflict.
Generic marketing terms, a search snippet, a landing page description or a
legacy positive boolean do not count.

## Continuity and replay guards
The receipt persists inside the **existing JSONB site_evidence**, so no new
database migration is required. Buyer readiness, ACP admission and raw prospect
promotion independently revalidate direct purchasing evidence. A legacy
REVIEW_READY row with an unproven explicit direct-buyer flag cannot silently
escape the newer gate. Company identity and personhood checks still apply.

Evidence freshness limit: 30 days; future timestamps beyond five minutes are
blocked. Missing canonical source URL, wrong-domain claims, missing timestamps
and malformed digests fail closed. Mixed buyer/supplier evidence always routes
to review, not automatic direct buying attribution.

Search-only Scout records keep their original heuristic as a *hint* but store
no verified direct-buyer type, score or boolean.

## Limitations / next upgrades
A source-text hash is not cryptographic proof a website made a claim. True
independent provenance would also preserve tamper-evident raw fetch artefacts,
signed fetch receipts and refetch proof; that is outside this change.

The current classifier uses conservative English phrase patterns; it is not a
semantic buyer-contract verifier. Quote attribution (testimonials/third-party
quotes), non-English pages and subsidiaries/verified email aliases require
further verification or manual review.

This phase performs no site scraping during tests, no live sends, no payment
writes, no founder approvals, and adds no service or timer. Observe-only
production acceptance still has to show a genuine review-qualified candidate.

## Acceptance tests
- Direct buying page yields a dated, bounded receipt; content hash
- Supplier/broker/marketplace or mixed pages block unearned direct status
- Search snippet and off-domain pages never establish purchasing proof
- DB holding persistence overrides unsupported high scores/legacy flags
- Buyer Review and both admission paths block old forged/stale direct claims
- Good sourced claims can still enter governed holding review
- No outbound, terms, payment or other execution authority is granted
