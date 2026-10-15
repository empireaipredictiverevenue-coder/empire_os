# Empire AI — first-party SEO enquiry-form privacy-link preparation

15 October 2026 | Existing website source only | ASTRA website-owner review / founder-gated publication

The SEO monetisation funnel must be useful and transparent **before** soliciting an enquiry. Both current commercial pages use existing first-party consented intake services, but the consent labels lacked an immediate link to the website's published privacy notice. This release makes the existing notice visible and keyboard accessible without changing legal wording, consent scope, submission API or data flows.

## First-party verification

- Live `https://empire-ai.co.uk/privacy`: HTTP 200, heading `Empire AI Privacy Policy`, existing text states last reviewed **14 October 2026**. This observation does **not** certify underlying legal/publication approval, accuracy or regulatory sufficiency.
- Live `https://empire-ai.co.uk/v1/checkout/commercial/offers`: responds `FOUNDER_LED_ENQUIRY_AVAILABLE` with available consultancy, avatar and existing priced intelligence-product options. It is a catalogue policy response, not evidence of product fulfilment or paying customers.
- `apps/empire-public-site/src/app/commercial/page.tsx`: adds exactly one same-origin `/privacy` link directly after the already-required one-to-one enquiry consent checkbox. Does not change consent text, data sent to `/v1/checkout/commercial/interests`, duplicate suppression, honeypot, offer selection or idempotency behavior.
- `apps/empire-public-site/src/app/predictive-revenue/page.tsx`: same one-link treatment for the existing deployment request; its `contact_consent`, no-unrelated-marketing limit, POST destination and existing submit behaviour remain unchanged.
- No analytics SDK, cookie, click-through referral, PPC pixel, affiliate API, social-tracking script, marketing opt-in, new lead database or extra public route was added.

## Isolated Next.js build evidence

`npm run build -- --webpack` compiled, typechecked and prerendered **17 routes** in a separate Git worktree. HTML inspection of `out/commercial.html` and `out/predictive-revenue.html`: each retains exactly one original form, exactly one required consent checkbox, exactly one in-form `/privacy` link, no third-party anchor and an existing submission button. This is an artefact build only. No live static files were copied; the production public gateway is owned by another active agent.

**Production release condition:** commit only two React source files, this documentation and regression tests. Do not copy worktree `out/` to production, install a new service, activate consumer `/roofing`, add a click tracker or restart the gateway without separate website-owner/founder approval and route regression. Live `/privacy` and `/terms` still need legal-owner and canonical-metadata review.

**Business outcome:** removes a clear transparency friction point ahead of the legitimate existing B2B enquiry flow. It cannot create search visits, accepted buyer terms or paid clicks on its own. Those must be measured independently in Search Console, canonical opted-in CRM and actual settled revenue.
