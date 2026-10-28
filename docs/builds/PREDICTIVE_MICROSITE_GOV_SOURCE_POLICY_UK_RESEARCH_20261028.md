# Predictive Microsite Factory — Country-Aware Official Source Validation

**Date:** 28 October 2026
**Owner:** existing Predictive Microsite Factory / SlopMonster research lane
**Branch:** `agent/predictive-microsite-slopmonster-20261026`
**Scope:** source validation and private research only — **not** website implementation, publication or acquisition

## What was broken

The original generic factory's `_fact_rows()` validator accepted HTTPS official-source URLs only from a small geographic pilot list. That blocked all properly attributed **UK government and council links** even for otherwise valid UK market research. The factory is intended to review 115 US/GB geography anchors, so this was a real research-source coverage defect.

## Minimal fix in the original factory

The same existing `empire_os.predictive_microsite_factory` now validates original source URLs using the already-verified `geo_registry` market country:

- **GB**: genuine `*.gov.uk` official public-sector hostnames, e.g. `www.gov.uk` and `www.manchester.gov.uk`.
- **US outside the original narrow pilot**: genuine `*.gov` domain hostnames.
- The original pilot's exact existing allowlist stays unchanged (no unrelated visual/site changes).
- All URLs still require HTTPS; no username/password, explicit port, query or fragment. Spoofed domains `gov.uk.evil.example`, cross-country hosts, HTTP, tracking URLs and code-like schemes fail. **No fetch occurs inside the factory**.

This validates **the link's government-host provenance only**, not whether a source supports a claim, whether it applies to a particular address, SEO quality or permission to publish. The existing site/source owner still independently reviews factual content and rights.

## Real private evidence of value: UK heat-pump research

The original `GB-MAN` Manchester market sample was reused as the sole input. No new territory market, service, agent, database, domain, timer, public release or website-worktree edit.

Three official information pages checked on 28 October 2026:

1. GOV.UK — [Check Boiler Upgrade Scheme eligibility](https://www.gov.uk/apply-boiler-upgrade-scheme/check-if-youre-eligible).
2. GOV.UK — [Current Boiler Upgrade Scheme grant options](https://www.gov.uk/apply-boiler-upgrade-scheme/what-you-can-get).
3. Manchester City Council — [Search planning applications by reference, address or postcode](https://www.manchester.gov.uk/planning-and-regeneration/planning/planning-permission/see-or-comment-on-planning-applications).

The private draft adds four practical, nonbinding checks: actual eligibility, current official grant terms, address-level planning status and confirmation of suitability with an appropriate installer. No address eligibility, contractor acceptance, verified lead volume, demand estimate or payable buyer has been inferred.

**Actual existing factory output**:
`/home/ubuntu/empire_releases/predictive_microsite_uk_source_research_20261028/review/`

- Source input retained privately at `../manchester_gov_research_input.json`.
- Exactly **1** reviewed candidate, **3** official source URLs, **4** research steps.
- Candidate `microsite_facd8e65d37634b91a6d` is **`HOLD_EVIDENCE`**, **0 publishable**, `published=false`, `stage_only=true`.
- Real measured keyword demand remains unsupported, and first-party GSC/forecast/outcome evidence was not attached.
- Original preview and private copy/design brief are **not published or indexed**, do not take enquiries and do not claim revenue.
- Private manifest SHA-256: `ca1646b36096d7b93741c90b16873504acfddff29df6684db04981314a391d77`.

### Test contract

`tests/test_microsite_official_source_host_policy_20261028.py` checks valid GB official domains, cross-country restrictions, non-pilot US government hosts, spoofing/query/userinfo/port/HTTP rejection, unchanged noindex/outbound status. Original source/copy and commercial outcome tests also apply. No external network calls or production release state mutation in tests.

## Next action for this original lane

Develop evidence-first research inputs across **source-distinct** nonpublished markets, only where legitimate current information exists and actual first-party demand can be attached separately. Use the existing factory and canonical original owner releases; do not treat staged draft count as a business outcome or build speculative location-swapped doorway sites.

The existing SEO/website/brand owners retain their separate workstreams. No cross-owner site work is part of this change.
