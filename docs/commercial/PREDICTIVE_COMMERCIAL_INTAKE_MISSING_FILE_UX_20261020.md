# EmpireOS — Commercial Intake: Missing File UX Repair

**Date:** 20 October 2026
**Owner:** Existing Predictive Intelligence release branch
**Authority:** OBSERVE / no customer contracts, marketing spend, procurement, CRM or agent dispatch

## What was wrong

The operator command

```bash
~/.local/bin/empire-predictive-observe commercial-intake /path/to/request.json
```

treated `/path/to/request.json` as a literal filepath. It is a **documentation placeholder**. Because no actual file existed there, `scripts.review_predictive_commercial_requirements_20261020._read` correctly rejected it but produced an unhelpful Python traceback. The Finance and cross-agent release board checks were successful and unaffected.

## Fix implemented

A new `commercial-template` launcher profile prints a complete **unfilled** JSON intake using the *existing* `empire_os.predictive_commercial_requirements.INPUT_FIELDS` contract. It does not select Tampa/roofing or any other country, industry, company, customer, lead quantity, source receipt or budget. The release includes the generator in its checksum manifest. The template is not an authenticated customer order and **cannot pass intake validation without a genuine specified market and requested quantity**.

The launcher `commercial-intake FILE` now detects a missing, unreadable or symlinked file **before** invoking the Python operator, exits nonzero, and prints an actionable message showing how to generate the blank template, **without a traceback**. Other malformed JSON, invalid industry/currency, forged owner receipts and unclear buyer/payment authority continue to fail closed in the original validation logic.

Release publication now smoke-checks `commercial-template`, `commercial`, `commercial-example`, `finance`, `owners` and the missing placeholder filename. It refuses to publish if the missing example path is accidentally accepted or emits a traceback.

## Correct usage on the EmpireOS server

```bash
# 1. Generate a BLANK draft; this local file is not a customer contract
~/.local/bin/empire-predictive-observe commercial-template \
  > /home/ubuntu/commercial_requirement.json

# 2. Fill in only the real source-supplied customer/founder requirements.
nano /home/ubuntu/commercial_requirement.json

# 3. Run the read-only evaluation
~/.local/bin/empire-predictive-observe commercial-intake \
  /home/ubuntu/commercial_requirement.json
```

At minimum, original `country`, `state`, `city`, `currency`, `industry`, `requested_qualified_leads` and relevant service types must reflect an actual instruction. Missing prices, customer role/authority, consent, inventory, vendor terms, unit cost and dates remain `null` or explicitly unconfirmed; **never fake verified receipts**. The engine's supported jurisdiction and industry taxonomies still apply. No company name, phone, email, lead record or personally identifiable data is needed in the draft; original scoped opaque source digests and source-owner receipts are separate.

For quick review without an actual requirement use `commercial`; for the **explicitly illustrative only** Tampa example use `commercial-example`.

## Tests and deployment

New `tests/test_predictive_commercial_intake_template.py` checks complete schema shape, empty customer/market/quantities, unverified authority, valid JSON printing and cross-industry draft review. Other full commercial and owner regression tests remain required.

The new release is an immutable version-pinned sidecar, **not a replacement of active production application services**. The previous release and its launcher rollback remain available. No automatic client onboarding, CRM writes, outbound, payment, material buying or forecasts.
