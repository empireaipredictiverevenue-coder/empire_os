# BSC USDT Smart-Contract Escrow

Status: local implementation and isolated tests only. No BSC mainnet deployment.

## Commercial lifecycle
1. Empire proposes an escrow-mode payment request.
2. A human approver verifies buyer, amount, beneficiary, terms and request window.
3. The requester creates the escrow on the approved contract.
4. The dedicated escrow verifier independently verifies `EscrowCreated` on BSC.
5. The payer funds the escrow with canonical BSC USDT.
6. Funding is verified from both the escrow event and matching USDT transfer.
7. Delivery/outcome occurs outside the custody contract.
8. The arbiter may approve release or refund with an evidence hash.
9. A safety delay allows dispute before execution.
10. Release/refund is independently verified on-chain before database recording.

Funding escrow is never actual revenue. A verified release is only revenue-eligible;
revenue recognition remains a separate governed accounting event.
## Contract controls
- Canonical token is BSC USDT `0x55d398326f99059ff775485246999027b3197955` on chain 56.
- Beneficiary is immutable after deployment.
- Escrow IDs are deterministically derived from Empire payment-request UUIDs.
- Payer alone can fund the approved escrow.
- Funding must arrive exactly; fee-on-transfer or short funding fails closed.
- `REQUESTER_ROLE`, `ARBITER_ROLE`, and `PAUSER_ROLE` are separated.
- Release/refund decisions require a nonzero evidence hash and a delay.
- The payer may dispute a funded or pending-release escrow.
- After `refundAfter`, the payer can reclaim funds even from disputed or pending-release state.
- Emergency pause blocks new funding and release to Empire, but does not trap refunds.
- There is no admin rescue/sweep path for escrow USDT.

## Verification controls
Every accepted chain proof checks chain ID, canonical block, confirmations, transaction
success, configured escrow address, deployed runtime-code SHA-256, exact escrow ID,
party, amount, and event provenance. Fund/release/refund also require exactly one matching
canonical USDT `Transfer` in the same transaction.
## Production deployment gate
Do not deploy this contract to BSC mainnet until all of the following are satisfied:
- external smart-contract security review/audit completed;
- mainnet constructor arguments reviewed independently;
- beneficiary is the approved Empire treasury;
- admin, arbiter and pauser are controlled by separately governed production identities;
- production decision delay is explicitly approved (target: hours, not minutes);
- deployed runtime bytecode hash is captured and pinned in verifier configuration;
- explorer source verification is completed;
- a small-value mainnet dry run proves create/fund/refund and create/fund/release paths;
- monitoring covers contract balance versus `totalEscrowed`, role changes, disputes,
  releases, refunds and pauses;
- Supabase escrow migration and dedicated verifier identity are approved separately.

The Hardhat dependency tree is build/test-only. `npm audit --omit=dev` reports zero
runtime dependency vulnerabilities; current development tooling still has transitive
audit findings that must be reviewed before the release gate is signed off.
