# Public Person-Contact Evidence Resolver Architecture V1

## Revenue problem

Empire has thousands of real buyer records and can recover named decision makers,
but many remain blocked because the named person has no verified person-bound
email. Generated email patterns are evidence candidates only and must never be
promoted unless SMTP verification succeeds on a non-catch-all domain.

## Canonical flow

canonical buyer
-> first-party people probe
-> named decision maker
-> native first-party/Hunter person-email evidence
-> exact-person public contact evidence resolver
-> generated-pattern SMTP verification (last resort)
-> existing contact verification gate
-> buyer review
-> GTM
-> governed outbound

## Resolver scope

The resolver performs bounded public observation only. It searches for the exact
known person and company, then inspects only:

- the company's own domain;
- explicit public government records;
- a small allowlist of business/professional directories.

A contact is emitted only when the inspected source explicitly binds the same
named person to an email. Page-level generic email presence is insufficient.

## Evidence ordering

1. Current first-party person+email evidence.
2. Existing Hunter-confirmed first-party person+email evidence.
3. Exact-person public evidence collected by this resolver.
4. Deterministic generated work-email patterns only when SMTP-confirmed and the
   domain is not catch-all.

Lower tiers never override conflicting higher-tier person identity.

## Promotion rules

- Person name must already pass Empire personhood rules.
- Existing decision role must meet the current buyer authority floor.
- The public source must explicitly expose the same person and email.
- External-directory emails must use the company's domain.
- Generic/role addresses are not converted into person-bound contacts.
- Existing merge_public_web_contact_evidence and verify_contact_plan remain
  the promotion authority.
- Directory evidence may support review, but cannot independently become
  send-ready unless existing outbound evidence rules allow it.
- No guessed email, inferred relationship, or search-snippet-only email is
  accepted.

## Operational bounds

- Maximum four exact-person queries.
- Bing-only bounded search providers to avoid slow broad-provider fallback.
- Maximum six unique result pages inspected.
- Maximum two pages per candidate source.
- Public-only retrieval.
- No database writes, outbound sends, terms, payment, or revenue authority.

## Failure semantics

No result, search-provider failure, page timeout, identity mismatch, off-domain
email, or ambiguous evidence returns no new contact evidence. The existing
buyer remains deferred; no gate is weakened.

## Authority

OBSERVE / evidence-only. This component cannot approve a buyer, authorize an
outbound intent, accept commercial terms, move funds, or recognize revenue.
