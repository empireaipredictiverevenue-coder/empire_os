# Empire AI — Predictive Revenue public enquiry admission
**12 October 2026 — tested code candidate; NOT DEPLOYED**

## Production truth

Read-only checks of the first-party gateway on 12 October returned HTTP 200 for the /commercial, /buy and /predictive-revenue pages and GET catalogues. The commercial offer API returned ten founder-led offers; Predictive Revenue returned five products; priced intelligence and Commercial Exchange catalogue responses also returned HTTP 200. A GET/catalogue status does not prove completed order creation, inbox notification, receipt, contracted delivery or verified revenue.

The actual /commercial founder-led enquiry proxy already required exact public Origin https://empire-ai.co.uk, browser Sec-Fetch-Site same-origin/none, JSON body, existing ephemeral request limiter and a 12 KB cap. The /predictive-revenue deployment-interest proxy originally forwarded arbitrary JSON POSTs without an Origin gate or rate limiter, with a 65 KB body cap. The backend's existing business validation and EmpireDB prospect-intake semantics were **not** sufficient to keep cross-origin abusive traffic out of the gateway.

## Minimal bounded repair

Modified **only** the existing `empire_os/public_gateway.py` Predictive Revenue interest POST route to:
- Preserve legitimate browser same-origin POSTs using the unchanged `/v1/checkout/predictive-revenue/interests` contract and the existing internal checkout service.
- Require JSON content type and exact configured `EMPIRE_PUBLIC_BASE_URL` Origin plus acceptable Sec-Fetch-Site, rejecting missing/cross-site Origin.
- Reuse the existing first-party ephemeral `FIRST_PARTY_INTAKE_LIMITER.allow(peer, "enquiry")` policy rather than implementing another agent, new database or rate-limit framework.
- Enforce 12 KB size limit and `Cache-Control: no-store` for accepted and denied responses.
- Fail closed on unavailable downstream checkout; never return request bodies, email addresses, internal API errors, signed terms or payment data.
- No new traffic permission, payment activation, mail sends, campaign write, external calls or backend/EmpireDB migration.

Negative and positive tests in `tests/test_public_predictive_interest_admission.py` mock the downstream service to avoid creating real leads: reject missing/foreign origins, cross-site browser fetches, plaintext, oversized submissions and rate-limited requests; prove a legitimate JSON first-party form request is still forwarded only to the internal endpoint. The existing direct POST test continues to reject non-JSON with HTTP 415.

**Rollout boundary:** This is a code-only change until founder-authorised public-gateway deployment. The current production service's last observed start was **12 October 10:45:49 UTC**, so it did not dynamically import this later candidate. Do not claim that external POST admission is protected until an independently verified post-deploy runtime proof. The existing shared proxy-IP bucket is conservative; assess real visitor ingress/proxy identity under an explicitly authorised load test before raising legitimate traffic. No outbound, live traffic, or production restart is authorised by this document.

## Revenue-relevant next proof

Read-only classify genuine inbound commercial interest by source and created-versus-existing prospect event, using canonical EmpireDB access and no PII exports, then verify an authorised founder/CRM review can access each request. If that receipt-to-founder path fails, do not send automatic replies or invent closing results; repair that bounded path after inspecting its live data contracts.

Buyer-side Lead Smart routing/ANI and recording evidence, Inquirly buy-box/source approval, LeadBank onboarding/sole-trader acceptance and Connexis concrete buy-box remain independent.
