# BSC / USDT Rail Convergence v1

Date: 2026-10-02
Status: ARCHITECTURE DELTA
Owner: Finance & Capital / Sales & Revenue

## Purpose

Remove executable ambiguity around the retired Solana/USDC rail.
The only active Empire commercial settlement rail is USDT on BNB Smart Chain.

This change does not move funds, create payment requests, approve payments,
recognize revenue, or expand authority.

## Canonical placement

Commercial terms / accepted order
-> fulfilment_order
-> payment_governance
-> BSC USDT payment request
-> independent BSC verifier
-> verified payment evidence
-> fulfilment
-> revenue truth.

Canonical modules:
- empire_os/payment_governance.py
- empire_os/bsc_usdt_verifier.py
- empire_os/self_serve_checkout.py

## Retirement rule

Solana, USDC, Solana Pay, Phantom, Anchor and Jupiter are prohibited in
executable production payment paths.

Historical documentation may mention them only as retired evidence.
Legacy executables must fail closed and point to the canonical BSC/USDT flow.
They must not poll chain state, build transactions, create invoices, mark
payments paid, or emit settlement links.

## Authority

Automatic: read/validate internal state only.
Founder/operator gate: payment proposal/approval as already defined.
Verifier role: independently verify BSC USDT evidence.
Revenue recognition remains separate and governed.
