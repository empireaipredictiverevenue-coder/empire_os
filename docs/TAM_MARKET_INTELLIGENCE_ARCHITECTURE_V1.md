# TAM / Market Intelligence Opportunity Classes V1

## Purpose

Close checklist check_26babb7b9f8a3ffa with a bounded Market Intelligence
foundation that can distinguish observed company coverage from verified TAM and
surface evidence-backed new-industry / new-country research opportunities.

## Diagram

Canonical resolved entities + public/registry provenance
        |
        v
TAM Market Intelligence
        |
        +--> observed market roster counts
        +--> explicit verified TAM evidence (optional)
        +--> new_industry research class
        +--> new_country research class
        +--> new_industry_country research class
        |
        v
Opportunity Factory / Radar research input only

## Truth contract

Observed entity counts are not TAM. A TAM count is available only when explicit
TamCountEvidence is supplied with source provenance and an observed timestamp.
Missing TAM remains UNKNOWN (None). Buyer intent, demand, price, margin and
revenue are never inferred from company counts.

Each company observation is tenant-bound and requires canonical entity identity,
industry, ISO-like country code, source reference and observation timestamp.
Duplicate observations for the same entity/scope are deduplicated while
provenance is retained.

## Authority

Mode is OBSERVE. The module cannot create prospects, send outreach, accept
terms, allocate buyers, move funds, recognize revenue, deploy code or expand
authority. Opportunity classes are research candidates only.

## Completion

Focused tests must prove UNKNOWN preservation, dedupe, verified-TAM separation,
tenant isolation, opportunity classification and no commercial/revenue
promotion. Live completion additionally requires a canonical runtime producer
and downstream Opportunity Radar verification.
