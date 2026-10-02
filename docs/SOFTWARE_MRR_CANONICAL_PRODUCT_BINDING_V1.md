# Software MRR Canonical Product Binding V1

## Problem

`software_mrr` is a routing lane, not a sellable product code. It must never
reach founder review, outbound intent creation, commercial terms, or checkout as
though it were a product.

## Canonical binding

Generic software-MRR buyers bind to:

- product_code: search_growth_command
- product_name: Search Growth Command
- billing: $299 USD per month
- catalog_state: VERIFIED
- version_state: VERIFIED
- binding_terms_ready: true
- minimum margin policy: 65%
- settlement rail: USDT on BSC

## Rules

Specific vertical/product routing continues to take precedence. The generic
fallback only applies when no more specific verified product has been selected.

Legacy buyer reviews carrying `software_mrr` preserve that original lane key
for audit, but founder-review presentation normalizes the proposed product to
`search_growth_command`.

No outbound authority is expanded by this binding.
