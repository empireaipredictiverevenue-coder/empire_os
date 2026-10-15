# Empire AI — safe canonical hostname release proposal, 15 October 2026

**State:** Code-only owner-review candidate. **NOT ACTIVE.** No Cloudflare, Next.js, FastAPI, DNS, service, checkout, identity provider, affiliate, website publication, traffic source, EmpireDB or paid media mutation.

## First-party evidence and intended result

Google Search Console on the authorised `sc-domain:empire-ai.co.uk` property has recorded search impressions for both `https://www.empire-ai.co.uk/` and `https://empire-ai.co.uk/` (and historical `http://www`), while the preferred homepage self-canonical is HTTPS non-www. On 15 October a bounded read found `https://www.empire-ai.co.uk/` returned **HTTP 200, zero redirects**; `http://empire-ai.co.uk/` also returned HTTP 200. This creates a hostname duplication *review* issue; it does not prove that Google will split rankings or that redirecting will cause uplift.

The Next.js site uses `output: "export"` and Empire's existing `empire-public-gateway.service` (FastAPI on 127.0.0.1:80) serves the built static content. **The hostname fix therefore belongs at the existing gateway/Cloudflare ingress, not in a separate Next.js server.** The production `empire_os/public_gateway.py` contains uncommitted edits owned by another agent. Do not overwrite or commit their work with this release.

## Prepared first-party candidate policy

`empire_os/public_canonical_host_review.py` is intentionally **pure and non-executing**. It previews an HTTP **308** permanent redirect from the literal `www.empire-ai.co.uk` Host header to `https://empire-ai.co.uk`, preserving only the tested same-site path and a small explicit UTM-only query whitelist. It does **not** inspect or trust `X-Forwarded-Host`, and has no FastAPI middleware hook.

Only GET/HEAD public content routes have redirect proposals: homepage, trust, industries and their well-formed slugs, commercial, predictive-revenue, published legal pages and the existing `/aeo/{niche}/{metro}` pattern. **Actual route publication must still be proved by the site owner** (a candidate is not an indexation or route release). For now the following all remain excluded: `/buy`, `/checkout`, `/roofing`, `/uk/roofing`, `/r/*`, `/v1/*`, OAuth/auth/identity paths, `/.well-known/*`, static Next.js assets, public A2A tools and unknown/unreleased pages. POST/PUT/DELETE/OPTIONS are never redirected. Queries with `code`, `state`, callback destinations or unknown parameters remain excluded. This restriction avoids exposing tokens, breaking consent paths or mutating commercial integrations while reviewing SEO.

## Owner release procedure — not yet authorised

1. Resolve ownership of the ongoing `public_gateway.py` modifications and inspect Cloudflare ingress TLS/host handling, including www and apex. A gateway redirect must use the canonical original raw Host only after confirming the trusted reverse proxy will preserve Host and cannot be spoofed. No fallback to unverified forwarded-header strings.
2. Confirm preferred URL for **each** allowed public route and correct redirect-vs-same-host response codes. Exclude all sensitive paths until their product owners validate full callback, payment, consent and affiliate flows. HTTP→HTTPS policy must be evaluated separately at trusted ingress; do not assume gateway local HTTP reflects visitor origin scheme.
3. Integrate the reviewed policy into the existing gateway **only** on a clean, owned release branch, add FastAPI TestClient tests for 308 location, preserved safe UTM, no redirect on signed/API routes and no redirect loops, then run gateway/full web/payment/SEO regression. No forced service restart or tunnel-rule mutation.
4. After explicit founder and website owner approval, deploy through the existing release workflow; verify external `www` requests, apex, static assets, legal notices, OAuth callbacks, payment links, browser security headers, CDN caching and Search Console before/after. Do not silently count a canonical redirect as a revenue or traffic gain.

**Remaining:** This policy is *proposed* and safely inactive. Search Console itself returns verified observations, while long-running Search Intelligence `/summary` still needs controlled service restart to load the code already tested in production that unifies status output. Buyer/CPC terms, outbound click attribution, source consent and any paid campaign remain separate founder gates.
