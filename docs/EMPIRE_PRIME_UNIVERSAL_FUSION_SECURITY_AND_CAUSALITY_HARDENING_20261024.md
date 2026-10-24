# EmpireOS PRIME — Universal Evidence Fusion security and causal lineage hardening

**24 October 2026 | Original Predictive Cloud / PRIME | OBSERVE only | Research branch, NO production release**

Continues original `feature/prime-universal-evidence-fusion-20261024` following commit `459faa497550a03b5940abf637eaba87c98226e5`. No second PRIME, source ingestion engine, data store, CRM, statistical model, ASTRA hierarchy, wallet or trading service was created.

## What was enhanced

1. **Source clock causality:** every incoming event must be both received **and observed** inside its source-family freshness envelope. Re-receiving an expired historical permit or another old event no longer makes it appear current. A corroboration or contradiction cannot reference a source record whose `received_at` is later than the referring record; temporal breaks are explicitly counted and place that entity in review HOLD.
2. **Cross-source independence:** a linked event must match both exact canonical entity and original tenant scope **and** tenant-binding digest before it can be counted as corroborating. Differing original binding digests inside one entity group place that entire group on HOLD. Explicit origin deduplication still counts repeated press articles as correlated, not independent.
3. **Revocation rehearsal:** original owner reviewers may supply a bounded optional SHA-256 event/origin deny-register to exclude revoked evidence **from a private pure review**. Underlying evidence is not read, changed, deleted or unlearned. This is NOT an authenticated revocation or consent system. The signatory, expiry and tenant/rights validity of the revocation source must be verified by the original Security/Data Cloud owners upstream. A removed source makes dependent references unresolved, creating explicit lineage HOLD rather than silent upgrade.
4. **Unresolved evidence:** when an event cites unavailable/revoked underlying evidence, `UNRESOLVED_LINEAGE_REVIEW_HOLD` is applied to that group; fabricated correlations are never scored as independent source proof.
5. **Privacy-separated outputs:** original `review_prime_universal_evidence` is explicitly an **internal research-detail packet** and is **NOT** a Founder-safe payload. `summarize_prime_founder_evidence` emits only bounded coarse record/group size bands, source family/class bands when cells have at least five observations, and negative authority/verification claims. No entity-group list, individual record, raw/hashed tenant/entity/source/event identifier, live buyer record or confidence estimate is returned. Group and family counts below five are not individually published. Aggregation is a safety reduction, **not formal anonymity or differential privacy**.
6. **Original predictive bridge integration:** `predictive_revenue_brain_bridge.build_predictive_revenue_brain_review` now returns the privacy-minimised aggregate under `prime_universal_evidence_shadow`, rather than the detailed internal group object. Existing independently gated original outcome calibration remains separate and untouched.

## Safety and limitations

- Owner-provided `ORIGINAL_OWNER_CUSTODY_REVIEWED`, `OWNER_REVIEWED_PERMITTED`, or `tenant_binding_sha256` **cannot authenticate themselves**. The pure function has no trusted issuer, source signature, secure venue session, verified live licence or actual original owner credential.
- SHA-256 digests of predictable people, company names or tenancy keys are pseudonyms, not safe irreversible deidentification. The original owner and Security must use approved purpose-scoped, secret-keyed identifiers (e.g. HMAC under independently managed keys) for future real adapters, never send the raw customer identifiers to PRIME, and honour erasure and suppressions upstream.
- Small-cell bands reduce incidental disclosure but do not prevent linkage inference or protect against repeated correlated queries; Founder authentication, rate controls and policy reviews remain required.
- The 5 commercial levels are **asserted evidence types, not statistical probabilities**. No owner-supplied apparent commercial commitment proves revenue. No trading observation can become a commercial calibration label.
- Negative evidence, NO_TRADE, no-enquiry and all missing or rejected outcomes must be preserved in the original owner-governed forward cohorts; this enhancement does not invent them, generate forecasts, adjust model weights or compute real-world precision.
- The optional revocation exclusion does not propagate deletions to existing immutable external databases, other readers, persisted derived caches or downstream published artifacts. Full security-owner-approved revocation/erasure propagation remains open.

## Exact verified testing

- Earlier scoped original PRIME/Quant/Source/CRM/Signal regression: **222 passed** before this hardening.
- Expanded hardened scope (same original modules plus additional adversarial source lineage tests): **232 passed, 1 external Starlette deprecation warning**, after the input/bridge hardening. This count is NOT an entire repository-wide test pass.
- Separate inherited broader collection blocker remains: original test `tests/test_economic_signal_materializer.py` imports `ECONOMIC_SIGNAL_SOURCE_KEYS` not defined by parent checkout `empire_os/intelligence_materializer_transport.py` at `813c55c...`; left unchanged, belongs to original materializer owner.

## Next build recommendation — no new product

**One authentic read-only source path, owner controlled:** Original Data Cloud + Security define a production-qualified signed/HMAC-scoped, revocable, permissioned summary receipt through existing source custody. Buyer Acquisition/Sales provides one legitimate original buyer-enquiry receipt only after tenant and suppression checks. Original PRIME/Scientific Agent retains the negative/NO_TRADE cohort and forward eligibility challenge, then uses the existing Economic Memory/outcome calibration for actual later results. Founder/Core/ASTRA review an authenticated private route with rollback before release.

**Release remains HOLD:** original production `/srv/empire_os`, EmpireDB, Smart CRM, Chief/ASTRA, buyer outbound/mailboxes, payments, wallets, live trading and independent Science/Risk decisions unchanged. No real buyer enquiry, profit, predictive performance or genuine authenticated source is verified by fixture tests.

**One EmpireOS. One Predictive Cloud. One PRIME. One canonical EmpireDB.**
