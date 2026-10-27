# Callmart Publisher Application — Original Commercial Workflow

Date: 27 October 2026. Programme: https://app.callmart.io/apply/publisher

## Application result

Empire AI's publisher application was submitted at **2026-10-27T14:03:32 UTC**. The official Callmart endpoint returned HTTP **200** and the message **"Application received. Our team will review it and follow up if it is a fit."**

The single original submission receipt is held in `runtime/buyer_network_intelligence/callmart_publisher_application_20261027.json` (mode 0600). It records source fingerprint and acknowledgement; it does **not** grant contract, traffic, buyer acceptance or revenue authority. **Do not re-submit automatically.**

Submission declared: Empire AI, contact Phillip Livesley, `phil@empire-ai.co.uk`, website `https://empire-ai.co.uk` (corporate site only), proposed life/final expense traffic, zero live insurance calls per day, owned first-party organic landing-page supply prelaunch, no live insurance campaign pages or paid ads. UK sole trader; asks for publisher eligibility, compliance, original buyer buy-box and payment terms.

## Integration

`inspect_original_callmart_publisher_receipt` reads only that exact original source receipt and reports `APPLICATION_SUBMITTED_AWAITING_CALLMART_REVIEW`, never `APPROVED`. The existing `observe_ops_adaptive_commercial` Ops Control includes `original_callmart_publisher_application` without a new timer, CRM, agent, scraper or outreach.

The original commercial reply watcher already checks connected Gmail accounts. Matching mail to the application should use real provider IDs and original reply history before any status promotion. No automatic send, buyer admission, contract signature, or activation.

The next actual step is waiting for **Callmart's acceptance or compliance/onboarding response**. Verify accepted insurance vertical, states and ZIPs, consumer disclosures, source requirements, reporting, payable connected-call criteria, scrubs/reversals, lead volume and payment terms before any pilot.

The application can be reviewed at the public official form: https://app.callmart.io/apply/publisher — **do not press submit again**.

Status: `SUBMITTED` / `REVIEW_PENDING` / `NOT_APPROVED` / `NO_INSURANCE_CALL_VOLUME` / `NO_REVENUE`.
