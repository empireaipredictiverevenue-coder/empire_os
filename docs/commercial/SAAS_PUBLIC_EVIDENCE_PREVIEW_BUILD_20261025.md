# Empire AI — SaaS Buyer Evidence Preview: Staged Web Build
25 October 2026 | Existing Predictive Revenue product + original public site | NO production publication

## Why this upgrade
The existing site already has a live guarded first-party Predictive Revenue catalogue and consent-based deployment-interest form. The original GET-only organic buyer journey observed 22 sitemap routes, **no blocking canonical/indexability issues**, two healthy commercial product/offer catalogues, and no enterprise route without a bounded path to a buyer form. The original Ops evidence observed **0 canonical first-party acquisitions** in one source-verified snapshot; this is not evidence that the internet has no interested buyers, nor proof of end-to-end CRM delivery.

The next honest improvement is to show a useful, public-data-free methodology preview *before requesting an enterprise deployment*.

## Implemented in the existing site source (staged, not published)
- **New** `apps/empire-public-site/src/components/SaaSRevenueEvidencePreview.tsx`.
- **Integrated** once after the Predictive Revenue hero in existing `apps/empire-public-site/src/app/predictive-revenue/page.tsx`.
- Interactive, keyboard-accessible `aria-pressed` selection between **Lead to demo**, **Trial to contract**, and **Deal to cash**.
- Each scenario defines three named stage evidence checkpoints, explicit *not proved* distinctions, and one business decision worth investigating. It has **no speculative percentages or customer figures**.
- The sample is openly marked *illustrative only; no customer data*. The CTA goes only to the same existing `#deployment-request` form already governed by the same specific contact consent, idempotent submission, webhook routing, product catalogue and no-binding-terms policy. No new form, cookies, analytics endpoint, pricing, automation, prospect store or external outbound.
- Clueso remains founder-*reported* sent and **no-repeat**; no LinkedIn reply or sale has been verified.

## Verified, without mutating production
- Existing on-host GET-only route audit: 22 sitemap routes; zero blocking route issues; Predictive Revenue route HTTP 200; commercial and Predictive Revenue read-only catalogues healthy. No POST test or real customer form submissions.
- `tsc --noEmit --incremental false --project apps/empire-public-site/tsconfig.json` passed.
- `node --test tests/test_saas_evidence_preview_20261025.mjs tests/test_predictive_interest_attempt.mjs` passed **7/7**. The Node tests explicitly verify the original consent and idempotency route, three interactive scenarios, honest evidence-only text and no alternative collection/send path.
- `pytest -q tests/test_review_live_organic_buyer_journey_20261024.py tests/test_public_predictive_interest_admission.py` passed. This protects existing same-origin first-party intake admission and organic buyer-path reporting.

## Release boundary
Changes are **source-staged only**. Do not claim visitors see the preview yet. The original public-site owner should perform the normal independent preview, render/mobile accessibility review, approved static build and hash manifest, and production release sign-off before deploying. Avoid running a Next build against the live out directory or replacing existing approved static files in this workstream.

No customer data was read or created, no new canonical enquiry/CRM row/payment, no message sent, and zero new revenue was verified. Treat free sample visibility as a way to begin a first authentic buyer conversation, not as a measured conversion improvement.
