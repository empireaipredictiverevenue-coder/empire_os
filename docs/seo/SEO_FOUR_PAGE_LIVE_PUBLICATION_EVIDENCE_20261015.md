# Empire AI / EmpireOS — SEO four-page public release evidence

**Publication date:** 15 October 2026 · **Existing server** `EmpireOS` · **Source production revision:** `824d1e46` · **Release scope:** four already-reviewed static pages, no service restart · **Founder instruction:** publish the SEO / PPC enquiry work now, preserve Astra's current site.

## Actual public release, not a preview

Four exact HTML files were atomically replaced via the existing `apps/empire-public-site/out` served by `empire-public-gateway.service`, while the unchanged FastAPI gateway stayed active:

| Public URL | SHA-256 release prefix | Verified public HTTPS result |
| --- | --- | --- |
| `https://empire-ai.co.uk/industries/roofing` | `599fc6b2ce23` | HTTP 200, exact HTML hash, H1 and canonical correct, new buyer qualification copy and original proposal CTA |
| `https://empire-ai.co.uk/industries/solar` | `c6f60c82cbd8` | HTTP 200, exact HTML hash, H1 and canonical correct, solar buyer/referral economics and original proposal CTA |
| `https://empire-ai.co.uk/commercial` | `a5b843e1ebdf` | HTTP 200, exact HTML hash, existing original form + required consent + in-form same-site privacy link |
| `https://empire-ai.co.uk/predictive-revenue` | `c98cc5d82eba` | HTTP 200, exact HTML hash, existing deployment interest form + required consent + in-form privacy link |

Nine new immutable Next.js CSS/JS/manifest assets were added without overwriting or deleting existing static assets; each was fetched over **public HTTPS and verified byte-for-byte** against local SHA-256. Every target public HTML response had its existing Content-Security-Policy header present. All four page URLs already appear in the unchanged existing sitemap (20 loc entries). The connected Search Console reported ready.

**Site protections:** `index.html`, `buy.html`, `roofing.html`, `industries/hvac.html` and `industries/property.html` were SHA-verified unchanged by the release. `/privacy` and `/terms` remained existing externally served HTTP 200 with their separate legal publication controls untouched. `/roofing` remains HTTP 200 with `noindex` and no new PPC, paid-click or buyer route. No Cloudflare, DNS, A2A, checkout, OAuth, affiliate redirect, database or lead transfer code was edited or service restarted.

**Custody finding:** During the 51-second isolated Webpack build, the existing commercial and Predictive Revenue static HTML files were replaced by another publishing process at approximately **18:40:42 UTC**, before the four-page release applied. The one-shot operator backed up **those latest pre-release files**, not stale copies. Their readable text, H1, legal link and first-party form count matched the newly built pages (visible text similarity 100%); the differences were build artefact hashes/markup. The release never overwrote concurrent source edits. The other owner's separate uncommitted legal-route changes in `empire_os/public_gateway.py` remain untouched.

**Reproducible release record:** `runtime/public_website/seo_four_pages_20261015_release_v1/{preflight.json,release_receipt.json,html/...}` in a mode-0700 first-party backup directory. Full before/after SHA-256 hashes, exact four allowed target files and nine new versioned asset names are recorded there. The new content was compiled from unchanged HEAD in isolated worktree `release/seo-four-page-live-20261015` with `npm run build -- --webpack`; 17 routes generated, full TypeScript compilation succeeded. The operator `scripts/release_reviewed_seo_four_pages_20261015.py` has explicit `--apply --approved-founder-four-page-seo-release-only` gating, collision/ownership protection, preflight, atomic replacement and automatic rollback of four HTML files if live loopback smoke checks fail. **23 focused regression tests passed**, including simulated failed-smoke rollback. Operator files are retained in the isolated release worktree and its Git branch; they do not create a new running agent or timer.

## Remaining SEO and PPC gates

- `www.empire-ai.co.uk` homepage still serves **HTTP 200**, rather than a permanent redirect to `https://empire-ai.co.uk`. We intentionally did **not** change the in-progress gateway owner's modifications. Existing root canonical is already present; owner can integrate the separately tested `public_canonical_host_review.py` policy after ingress, auth, checkout and CDN reviews. This canonical redirect is not required to keep the four content pages public.
- These are useful first-party pages, not proof of Google indexing, actual ranking gains or form conversions. Compare their GSC and consented founder commercial enquiry results after Google processing lag and only claim verified data.
- A public affiliate programme **does not create a payable CPC contract**. Keep publisher pay-per-click redirects, call routing, buyer delivery and paid search disabled until actual signed buying terms, accepted territory/source, consent and finance reconciliation. The existing warm US roofing buyer and SolarBriton contacts remain separately governed.

**Final state:** FOUR PUBLIC SEO PAGE RELEASE SUCCEEDED; full public HTTPS/asset hash checks succeeded; no new infrastructure, service restart, ad spend, payment or live outbound.
