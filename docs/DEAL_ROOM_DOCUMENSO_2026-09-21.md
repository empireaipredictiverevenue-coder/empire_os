# Empire Deal Room / Documenso Bridge — 2026-09-21

## Canonical role

The Deal Room is the agreement-evidence stage between verified commercial terms and payment readiness. It does not make a quote, signed document or payment request equal revenue.

Flow: buyer conversation -> verified commercial terms -> agreement draft -> founder/counterparty approval -> Documenso envelope -> verified completion webhook -> canonical agreement evidence -> payment readiness -> verified BSC USDT payment -> fulfilment -> outcome -> recognized revenue.

## Provider contract

Current Documenso v2 uses the envelope API:
- base URL: https://app.documenso.com/api/v2
- create: POST /envelope/create
- distribute: POST /envelope/distribute
- canonical identifier: envelopeId

Webhook requests are verified with the configured X-Documenso-Secret using constant-time comparison. DOCUMENT_COMPLETED only becomes verified agreement evidence when the envelope is COMPLETED and every required SIGNER/APPROVER action is complete.

Official documentation:
- https://docs.documenso.com/docs/developers/api
- https://docs.documenso.com/docs/developers/webhooks
- https://docs.documenso.com/docs/developers/webhooks/verification

## Authority

Current Empire implementation is preview/evidence-normalization only. Provider creation/distribution, legally binding acceptance, payment request creation, funds movement and revenue recognition remain separate governed actions.

empire_os/deal_room.py normalizes provider evidence into the same canonical agreement shape consumed by First Revenue Proof. Unknown or incomplete provider state remains unverified.
