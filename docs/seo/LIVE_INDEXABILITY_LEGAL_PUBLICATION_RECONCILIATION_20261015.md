# Empire AI | First-party SEO indexability truth — 15 October 2026

**Review scope:** existing `empire-ai.co.uk` property only, read-only HTTPS. **Owner:** SEO Director and website/legal owner. **Execution:** OBSERVE. This is a technical status report, not legal approval, a Google indexing certificate, buyer consent or revenue evidence.

## Live evidence

After correcting an outdated rule that expected legal URLs to return 404, the original one-hit owned-domain indexability operator completed successfully at `/var/tmp/empire_owned_seo_legal_live_truth_20261015.json`:

- **20 sitemap URLs** observed from the existing sitemap, **20 with technical indexability signals**, **0 technical issues detected in this bounded check**. The audit checks HTTP 200, expected title/H1 and canonical signals. It does not prove actual indexing, helpful-content quality or commercial conversion.
- `/roofing`: HTTP 200 with `noindex`; **buyer-facing consumer acquisition remains gated**. Never remove `noindex` or activate calls without verified downstream terms, consumer/privacy requirements, quality and founder authority.
- `/roofing/replacement-vs-repair`, `/roofing/installation-checklist`, `/research/agent-governance`: still held from public publishing by the existing release gate; any accidental HTTP 200 remains a hard rejection.
- `/privacy` and `/terms`: currently public HTTP 200. Their present metadata has title/H1 but **missing matching canonical tags**. These pages are publicly served by the existing website; this readback cannot verify which operator published them or whether legal/publication sign-off was granted. Both remain review items, not automatically removed or redirected.
- No website writes, ad spend, outbound, Google indexation request, EmpireDB mutation or payment occurred.

## Patch scope

Reuses the SEO Director's existing bounded first-party indexability reviewer and one-hit probe instead of a new service, crawl timer or SEO agent. It changes only legal-route classification: legal HTTP 200 is public observed metadata requiring owner review, not a failed unreleased-guide gate. Buyer `/roofing` noindex and unpublished article gates stay fail-closed; sitemap input remains bounded, HTTPS-owned only, and raw HTML is not persisted. The legacy `expected_gated` field remains compatible, with explicit legal-public visibility notes; downstream approval is never inferred.

## Concrete SEO fixes for website owner

1. Review missing canonical metadata on `/privacy` and `/terms` against the actual published legal copy and site policy. Do not unpublish legal documents automatically.
2. Review `https://www.empire-ai.co.uk/` and `http://empire-ai.co.uk/` both serving HTTP 200, vs the preferred `https://empire-ai.co.uk/`. Plan one origin-level 301/308 canonical redirect preserving all site paths/queries, static assets, OAuth callbacks, legal pages, checkout, API and public A2A routes. Confirm Cloudflare host routing and browser/security effects before any change; public gateway is concurrently edited by another owner.
3. Keep original, sourced, people-first `/industries/roofing`, `/industries/solar`, `/predictive-revenue` content reviews. No mass 210-page AEO release, buyer click redirects, CPC advertising, bought clicks or assumed revenue.
4. Search Console has real daily data, but the long-running Search Intelligence service was started on 10 October and its `/summary` still presents a stale disabled Search Console status while `/search-console/status` reports ready and authenticated observations return real data. The **current repository source already fixes this mismatch** and the existing status tests pass; only a separately controlled restart of `empire-search-intelligence-api.service` can reconcile the running process. Do not rotate keys or claim credentials are missing.

## Production checks

Commit this isolated audited reviewer only when new paths do not conflict with another agent's work; run tests in the exact production tree before release. Keep the existing SEO timer, site service, outbound, payments and EmpireDB unchanged. All revenue remains contingent on signed buyer terms, accepted payable events and settlement evidence.
