# Empire Analytics — Campaign Click / Intent Evidence Bridge

20 October 2026 | Founder-commissioned enhancement | **Source-only, no live activation**

## Why this exists

Video reference: https://youtu.be/jXxjKAz1Org — Taylor Haren's email-click,
website-interest and retargeting strategy. We need to distinguish campaign
URL claims, attributable clicks, qualified visits, sales conversations and
paid orders rather than treating email replies as the only signal.

Reuses the existing `empire_os/analytics` package and offline consent-aware
event contracts. There is no second CRM, analytics database, outbound agent,
click collection service, or paid provider.

## Implemented here

- `empire_os/analytics/campaign_click_evidence.py` adds a scoped, versioned
  HMAC-SHA256 opaque link-token contract. Tokens reveal only a random nonce,
  issue/expiry seconds and signature. Tenant, campaign, asset, recipient
  lookup and destination are private registry bindings covered by the MAC.
- Rejects unknown tenant/campaign/link IDs, PII-like recipient lookup keys,
  arbitrary destinations/open redirects, unsupported channels, weak keys,
  invalid lifetime, expired/future tokens, and altered registry bindings.
- Link issuance is refused for suppressed, revoked or unknown contact permission.
  Verification of a link **does not** claim a person, site visit, human click,
  engagement, conversion or revenue was observed.
- Offline gateway-receipt review requires trusted, owner-operated gateway and
  recipient-link registry resolvers. It deduplicates event IDs, checks time
  bounds, rejects unverified gateway or registry proof, discards scanner signals
  from human-interest candidates, holds uncertain/suppressed interactions and
  returns **aggregate-only** non-identifying counts. It also counts
  multi-asset review groups when distinct campaign links have suspected-human
  gateway receipts for the same private recipient binding. No recipient keys
  leave the review and the group is not a verified human or buying intention.
- Callback failures never leak external exception text, raw prospect/email
  data or signed link identifiers.
- No API, public link, redirect, pixel, cookie, deployed collector, DB write,
  email send, retargeting export or autonomously triggered sales follow-up.

## Integration handoff — existing owners (not separately implemented)

1. **Email/Sales Director owner:** Register campaign, link, intended
   recipient and contact-permission evidence in canonical tenant-scoped CRM.
   Only publish signed recipient links within an appropriately assessed
   marketing channel. Provide a stable opaque nonce -> private binding lookup.
   Unsubscribes, do-not-contact, source permissions and suppression must be
   rechecked at action time. Never treat scanner/preview traffic as a human.
2. **ASTRA/Public website owner:** Implement an explicit approved first-party
   gateway route only after privacy review. Do not blindly turn a token
   into a redirect or fire analytics scripts. Destinations must be fixed and
   allowlisted; reject malicious hosts/URL parameters. Apply abuse limits,
   retention/erasure and logging minimisation.
3. **Empire Analytics owner:** Establish a trusted, server-enforced
   permission/consent authority appropriate to the specific click or analytics
   purpose. Wire reviewed gateway receipts into the existing EmpireDB analytics
   ledger (migrations 054/055 are not yet production-verified). Session/page
   tracking and retargeting require their own valid permission/basis.
4. **CRM/Predictive Revenue owner:** Show appropriately authorised
   evidence-backed follow-up candidates in a private, tenant-isolated
   workflow. A signed link plus suspected-human classification is a weak
   interest signal, **not** a verified person, prospect enquiry, lead,
   appointment, revenue event or retargeting permission. Require additional
   signal and manual/compliant decision before contacting anyone.

## Production truth from the 20 October read-only checks

- Homepage Tag Intelligence monitoring exists, but observed static markup
  did not verify GA4/GTM/Google-tag configuration or any live event delivery.
- Existing analytics first-party collector is not production-verified.
- EmpireDB Analytics054/055 schema is not deployed in the observed catalog.
- The private Analytics console release has owner/source compatibility holds.
- No real campaign-click, contact identity, retargeting, conversion or revenue
  totals can be derived from this patch.

## Release requirements

No live instrumentation until the existing owner establishes the gateway,
server-side receipt/source signature authority, consent/privacy controls,
approved retention/erasure, CRM isolation, tested automation filtering and
an actual production integration smoke. Do not conflate marketing-contact
permission with website analytics consent, or token possession with human intent.
The private Sales Director can show evidence classes only when grounded.

## Verification

```bash
cd /home/ubuntu/empire_worktrees/campaign_click_intent_bridge_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/analytics/test_campaign_click_evidence_20261020.py
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m py_compile \
  empire_os/analytics/campaign_click_evidence.py
git diff --check
```

This handoff assigns no other agent's work and grants no production authority.
