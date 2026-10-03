# EmpireOS — All Products Pre-Market Gauntlet V1

Date: 2026-10-02
Status: ARCHITECTURE CONTRACT
Change class: Commercial/product verification architecture

## Purpose

Verify every canonical Empire commercial product before campaign activation.

The gauntlet is product-code complete, not merely family-level. Every current
catalog row receives an explicit readiness classification and fail-closed verdict.

## Product universe

Primary commercial universe:
- every row in runtime/commercial_catalog/latest.json.

Additional proposal-only products:
- Digital Avatar Copilot;
- Digital Avatar Workforce;
- Digital Avatar White-Label Workforce.

Proposal-only products are tested for pricing/package consistency but are NOT
merged into canonical catalog readiness until separately governed activation.

## Canonical classifications

For each catalog product:

### verified_sellable
All must be true:
- active=true;
- catalog_state=VERIFIED;
- version_state=VERIFIED;
- price_basis VERIFIED;
- acquisition_cost_basis VERIFIED;
- fulfilment_cost_basis VERIFIED;
- margin_policy VERIFIED;
- binding_terms_ready=true;
- canonical public catalog projection includes the product.

### active_pending
- active=true;
- one or more canonical readiness gates incomplete.

Must NOT appear in public verified catalog projection.

### inactive_recovery
- active=false.

Must NOT be sellable or publicly projected regardless of historical product
identity or pricing remnants.

## Family integration coverage

In addition to per-row catalog verification, the pre-market gauntlet runs
integration suites for:
- search intelligence / SERP / crawler;
- solar opportunity maps;
- permit intelligence;
- property intelligence;
- private-capital intelligence;
- managed opportunity intelligence;
- Predictive Revenue products/demo/private deployment;
- Commercial Exchange seats;
- recovered MRR products;
- business/data products;
- fulfilment observation;
- commercial terms / usage / pricing verification;
- checkout/payment/revenue gates;
- Digital Avatar packaging/economics.

## Truth rules

Green engineering tests do not override catalog truth.

A product with passing code but incomplete commercial evidence remains pending.

A recovered product with historical code/pricing remains inactive until its
current canonical economics/terms/fulfilment are re-verified.

No synthetic evidence may be created to move a product category.

## Campaign gate

Catalog verification alone is insufficient.

Campaign claims/offers may only use products that are BOTH:
- verified_sellable in canonical commercial truth; AND
- supported by an explicit current production smoke-evidence reference proving
  the real read/fulfilment path for that exact product code.

A verified product without current smoke evidence remains campaign-blocked.

Research/demo/proposal flows may discuss blocked products only when clearly
labelled and must not present them as currently purchasable/fulfilled.

Digital Avatar campaigns remain blocked until its pre-market product gauntlet
and governed catalog activation path are complete.

## Irreversible actions

This gauntlet performs no:
- outbound send;
- checkout creation;
- payment request;
- funds movement;
- binding commercial term activation;
- live meeting join;
- revenue recognition.

## Verification output

Produce:
- total catalog rows;
- verified_sellable count/codes;
- active_pending count/codes/blockers;
- inactive_recovery count/codes;
- duplicate/malformed product codes;
- public-projection consistency;
- proposal-only Digital Avatar checks;
- campaign_ready product-code set;
- campaign_blocked product-code set.

Any unclassified row or duplicate product code fails the gauntlet.
