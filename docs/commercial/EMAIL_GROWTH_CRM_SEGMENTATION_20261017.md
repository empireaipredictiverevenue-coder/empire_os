# Empire AI — Owned Email Audience + CRM Segmentation

17 October 2026. Reuse EmpireOS / EmpireDB / Resend. No new mail infrastructure, migration or scheduler.

## Completed and verified

- Existing CRM read-only segment preview now also classifies industry, lifecycle cross-segments, and editorial interest hypotheses from canonical prospect niche and linked lifecycle records. It never infers audience permission from names, text, commercial enquiries or forecasts.
- Suppressed, opted-out, bounced and do-not-contact contacts cannot be editorial interest candidates. Unknown niche remains unknown. The CRM tenant-scoped page is NOT a verified complete audience. Email identities and subscriber lists are not exposed.
- Authenticated newsletter-purpose consent and person-scoped suppression are NOT part of the current CRM view. A buyer consenting to a direct reply has NOT consented to marketing. No user has been imported into Resend from CRM or cold data.
- Resend verified domains: mail.empire-ai.co.uk and empire-ai.co.uk. Open/click tracking remains off. Original General segment preserved.
- Three Resend topics created, ALL default opt_out:
  - Empire AI | Predictive Revenue : 26281fb4-c19b-46a5-8873-619b41c6e52e
  - Empire AI | Search & AI Visibility : c269ddbe-8d2a-4329-a9a3-e8a0f870d435
  - Empire AI | Industry Opportunity Signals : 55ffe293-0a1f-47ba-8611-68e28c86db2a
- Two new empty-purpose segments created (no subscriber enrolments):
  - Empire AI — Predictive Revenue Subscribers : cba0eebe-beec-4f7a-a536-6e37d2ea5247
  - Empire AI — Search & AI Visibility Subscribers : 2d0df2b8-e643-48d8-a681-1b8818306a82
- No third Industry segment: Resend rejected creation because current plan supports three segments total including General. Do NOT pay for an upgrade solely to add a segment or enrol unrelated General contacts.
- First real newsletter ISSUE 01 created in Resend as a DRAFT ONLY: 0e2a43c7-7ba4-4d0f-83e3-fb3ca74f402f. Subject: Three numbers to check before paying for AI. Segment: Predictive Revenue Subscribers. Verified status draft, no send or scheduled send.

## Next integration for ASTRA: do not rebuild the site

Add a premium Intelligence Brief newsletter invitation after critical site visuals. Selectable unchecked topic preferences, clear newsletter purpose and cadence (e.g. fortnightly), /privacy notice, optional email address and a working opt-in confirmation path. The signup must never silently use consent given on /commercial, import CRM prospects or display a fake success message.

Reuse existing public gateway, canonical EmpireDB, and Resend with server-owned credentials. Build a consented, idempotent capture/confirmation process with rate-limits, person/topic/purpose proof, suppression/unsubscribe checks and sender authorization. Until server-side recording and a genuine confirmation path are ready, show a non-form invitation/teaser, not a broken live form. Avoid adding new servers or databases.

## Operating logic

- CRM industry, lifecycle and editorial-interest segments are automated *review projections*, NOT subscribe-to-marketing authority.
- A marketing subscriber must explicitly choose an email topic; do not add anyone via prospecting, scraping or purchase. Always honour opt-outs, hard bounces and suppression.
- Predictive Revenue, Search & AI Visibility and industry opportunity education are distinct editorial interests; people can change preferences.
- Campaigns remain drafted for founder review until a genuinely opted-in audience exists. Only verified provider delivery and canonical EmpireDB commercial outcomes count as delivery and revenue; do not infer opens/clicks while tracking is off.

DONE: read-only CRM multi-dimensional segmentation, Resend preferences, two purpose segments, first draft broadcast.
NOT DONE: functional signup and confirmed opt-in, subscriber syncing, segmentation-based campaign automation, email delivery, and revenue attribution. NO subscriptions, public deployment or outbound authority was created by this work.
