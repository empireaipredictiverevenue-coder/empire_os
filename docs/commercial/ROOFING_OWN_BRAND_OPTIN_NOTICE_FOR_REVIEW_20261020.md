# Empire AI — homeowner email opt-in privacy notice (review draft)

**Status: DRAFT FOR FOUNDER/PRIVACY OWNER ONLY. Do not publish or activate signup based on this draft alone.**

## Suggested short form notice

"Receive optional Empire AI homeowner guides and service-research updates by email. We'll use the address you provide for these own-brand emails and to manage confirmation, unsubscribes and privacy requests. You can read our free roofing cost guide without subscribing. You can unsubscribe from each email or contact us using the Privacy Notice. We will not pass your contact details to roofing contractors or other buyers because you subscribe to Empire AI updates."

Checkbox default: **unchecked**. Button: "Join optional homeowner updates". Display a link to the current public `/privacy` notice. A user who requests a free guide is **not** subscribed without checking the box and completing any required verification.

## Required public privacy details to confirm before using this text

The currently served `/privacy` URL is HTTP 200 but does not specifically enumerate this subscriber purpose. The existing site's legal owner must check and approve:

- Identity/contact details of the lawful controller and a functioning contact channel for data rights requests
- Exactly what information is collected: the submitted email, time/notice version, scope of the own-brand choice, send/confirmation/unsubscribe receipts, and suppression data
- Lawful basis for optional own-brand email updates (explicit electronic-marketing consent wherever required); no bundled referral consent
- Purpose-limited processors including the actual transactional provider, international transfer arrangements if applicable, and approved custody of the original email and encryption keys
- A concrete data retention policy for pending, verified, withdrawn, bounced and erased statuses; suppression safeguards and access limitations
- How to stop email marketing, request access/correction/erasure, withdraw consent, and complain to a competent regulator
- How the first-party system identifies subscribers, corrects mistakes, handles bounced addresses and resolves disputed consent
- The separate, recipient-specific and channel-specific disclosures/consent required **before a named contractor or any other Lead Exchange buyer could receive an individual's details**

Do **not** claim that subscribers have chosen a specific roofing provider, requested a quote, are homeowners in a verified ZIP, or are qualified appointments. All such claims need original evidence and separate permission.

## Approved transport and implementation evidence available

Read-only provider account inventory on 20 October 2026 showed `mail.empire-ai.co.uk` and `empire-ai.co.uk` both verified for sending on Resend; the account has no open/click tracking enabled for these domains. The original server has a private `resend.env` with a `RESEND_API_KEY` configuration field, but the **subscriber** runtime has not been granted sender authority and no API key value is included in code or this document.

An isolated transport adapter implements first-party, confirmation-only `POST /emails`, sending as `Empire AI <updates@mail.empire-ai.co.uk>`, with `reply@mail.empire-ai.co.uk` as reply-to. It requires a fresh independently verified suppression lookup, separate owner approval, a scoped API key, and uses a recipient-free idempotency key; no marketing bulk path. The private backend is not connected to production Resend or EmpireDB.

The staged subscriber tables are absent from production. Privileged backup inventory could not be read in the current remote session; applying migration 057 requires a confirmed recent backup plus independently scoped DB roles/RLS. The public guide and preferences page remain gated by the existing exact-content release controls.

### Required outcomes to mark truly live

The original website/legal owner approves and publishes the correct notice; DBA authorises and readbacks the exact migration with limited private subscriber roles; Resend/subscriber owner verifies a real confirmation and withdrawal receipt with a consenting test participant; the live privacy link and unsubscribe mechanism remain usable with new signups paused. Only then should the public subscription readiness endpoint return `OPTIN_COLLECTION_ENABLED`.

**Prepared source does not constitute consent approval, confirmed email delivery, a buyer lead, or revenue.**
