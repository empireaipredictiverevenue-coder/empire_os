# Empire AI — existing SEO / AI Search integration release (26 October 2026)

Owner: Search Intelligence and the original weekly GSC owner. This release reuses the original EmpireDB PostgreSQL and systemd services. It does not install an agent, database, search API, crawler fleet or timer.

Deployed source scope: original weekly Marcus/GSC Keyword Universe enhancement; original earned authority read-only reconciliation; Google indexed-version read-only fixed five-URL module, CLI and loopback Search Intelligence API route; research docs and regression tests.

API route: GET http://127.0.0.1:8771/v1/search/search-console/indexed-version/fixed . Exactly five fixed own-domain URLs. This calls official Google Search Console URL Inspection for Google's indexed version, using existing read-only adapter/service-account authority; no live URL test or URL submission. Absent/invalid source gives bounded 503 without credential detail. Its only listening listener remains 127.0.0.1. One GET can make up to 5 Google API read calls; do not expose it via public website, poll it frequently or imply Google updates its index.

Backlink reconciliation is deliberately a typed read-only module, not a database activation. The verified Agenstry observed anchor should be admitted to the existing canonical backlink evidence owner only after tenant/rights/source/dedup review. The canonical repository currently has zero stored rows and is runtime-gated. Historic Common Crawl domain candidates, publisher research and on-site links must not be inflated into verified links.

The Marcus/GSC weekly integration uses the SAME original one local GSC GET and existing timer. It retains up to twelve real, validated, unmatched query/page rows for private semantic review, does not label keywords as confirmed buyer demand, and omits email-like queries. No new timer, extra model calls or publication.

An unrelated website source change and four-page static publishing candidate remain a distinct guarded site-owner release; never replace existing live October 20–24 pages with stale generated assets. Existing website mutations and consent/payment/outbound gates remain unchanged by this API/search release.

Rollback: installer records exact before/after hashes and backups under /home/ubuntu/empire_releases/seo_unified_existing_stack_20261026_v1/, preserving file modes. If post-deploy tests fail, restore preimages and reload original Search API process. Never revert unrelated files.

Hardening correction before activation: original Google inspection API route has one shared process-local 6-hour successful-report cache (five Google calls maximum per success refresh) and a five-minute failure cooldown, guarded by a lock. It catches provider HTTP errors and returns generic 503 without disclosing credentials. Verified in original TestClient tests with repeated GETs; no independent new provider/token account.

## Original supervised source and parser feature installation

Additional reviewed original SEO Spider feature:
- search_intelligence/targeted_referrer_spider.py — strictly bounded reviewed-source HTTP crawl, only if explicitly invoked with a reviewed graph, selected exact public HTTPS hosts, a private evidence destination and --approve-bounded-public-reads.
- search_intelligence/backlink_live_verifier.py — SSRF-resistant public TLS pinning, robots and bounded host/page caps; never treats Common Crawl as a verified live link.
- search_intelligence/historical_spider_seeds.py — local historical WAT candidate seeds only.
- scripts/review_targeted_referrer_spider.py — --review-only default only when explicitly set by operator; no service/timer registered.
- empire_os/scrapling_source_evidence.py — OFFLINE source-governed HTML evidence parser (does not fetch). Optional Scrapling dependency remains optional; one test skipped where unavailable.
- Associated original regression tests: 86 passed, one optional dependency skipped on the unified current source tree.

These are recovered owned components, not automatic outbound, new crawling rights, qualified leads or new backlinks. Specific third-party collection still requires per-source terms/robots/crawl budget/supervised action and direct acceptance of proof.
