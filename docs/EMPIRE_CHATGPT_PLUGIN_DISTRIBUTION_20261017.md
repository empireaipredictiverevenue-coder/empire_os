# Empire AI → ChatGPT Plugins Distribution Plan (2026-10-17)

**Goal:** make Empire AI discoverable as useful tools in ChatGPT/Codex with one existing EmpireOS backend. **Not:** create new servers, duplicate CRM/data infrastructure, or imply listing approval.

## Important 2026 OpenAI policy facts
Official docs:
- https://developers.openai.com/plugins/quickstart
- https://developers.openai.com/plugins/build/plugins
- https://developers.openai.com/plugins/deploy/connect-chatgpt
- https://developers.openai.com/plugins/deploy/submission
- https://developers.openai.com/plugins/plugin-guidelines

A published plugin may include an MCP server and a skills package. Current public Plugin Directory publication requires verified publisher identity, a package ZIP, scans, test/reviewer instructions and approval.

**Monetisation restriction:** As of October 2026 the plugin guidelines do NOT allow plugins to sell or promote digital subscriptions/services, including freemium upsells. An existing paid subscriber can authenticate and use their entitlements; the plugin can explain why an unavailable capability requires a different plan and link to neutral informational plan details, but may not link directly to subscription checkout or push users to upgrade. Physical-goods checkout is a different eligibility path. Accordingly avoid in-chat sales prompts, tier advertisements, upsell-only tool results or payment handling. The independent Empire AI website can pursue SaaS customer acquisition outside this plugin (subject to applicable laws and policy).

## Product choice
First public candidate: **Empire AI YouTube Intelligence** (after live official YouTube API connection and actual quality validation). One sharp user benefit: competitor-video comparison using same-channel, same-age-band and duration proxies, with first-party research context. Do not claim proprietary watch-time, hidden competitor retention, transcripts, search volumes, buyer intent or accuracy superior to vidIQ without measurement.

Potential later: **Empire AI ROI Analysis** (source-linked explicit input assumptions, zero fake predicted revenue), **Empire AI SEO Opportunity Analyst**, **Empire AI Commercial Intelligence**. Each requires independent utility and review; no mass-upload of half-ready listings.

## Existing foundation / boundaries
- Existing EmpireOS repo `/srv/empire_os`; Media OS reader `empire_os/youtube_read_adapter.py`; benchmark `empire_os/youtube_intelligence.py`; CLI `scripts/review_youtube_video_readonly.py`.
- Existing **internal** `empire-ops-mcp` (:8765, `empire_os/ops_mcp.py`) has repository read/write and privileged operational tools. **NEVER publish or reuse it as a consumer plugin endpoint.**
- Do not route outside users through founder CRM, canonical EmpireDB, admin ops, secret-bearing env or paid inference. Future consumer-facing MCP connection must expose a separately scoped *public service surface*, backed by existing tested read-only modules and tenant isolation.
- Existing Cloudflare and web gateway can host a bounded public route if reviewed, not a new server. Do not activate, change DNS, deploy live gateway route or expose internal port without explicit founder approval.
- Dedicated OAuth account auth (where used), entitlement resolver, rate quotas, minimal scopes and server-side tenant boundaries. Do not trust tool parameters for access or charge access automatically.

## Phase gates
1. **Evidence readiness:** validate official YouTube Data API credentials through current adapter. Presently no key was found in inspected runtime env; customer tool cannot promise current competitor data. Add public API caching, limits and request budget, with accurate citation/observation timestamps. Produce real fresh benchmark against at least 3 source channels; no fabricated metrics.
2. **MCP tools:** expose only independently useful operations, each independently tested:
   - `review_public_youtube_video` (verified public title, author and source; no unsupported transcript or watch claims).
   - `compare_competitor_videos` (official Data API rows, actual cohort and source refs; may hold if samples insufficient).
   - `prepare_content_research_brief` (evidence and original editorial concepts, no copied third-party work).
   Do not expose generic shell, SQL, environment inspection, CRM mutations or payments. Set annotations explicitly for readOnly, destructive, openWorld.
3. **Publication package:** Agent Plugins portable root `plugin.json`, root `mcp.json` with one verified public streamable HTTP MCP URL, optional `skills/` and approved brand assets. Do NOT guess/advertise an endpoint, put keys in ZIP or include `apps/.app.json` or lifecycle hooks; these are not accepted for this public submission flow.
4. **Testing:** MCP Inspector; private ChatGPT plugin via Plugins → Add custom MCP server; 5 meaningful positive and 3 negative tests, both mobile+desktop, full access/empty result/rate limit/no-title scenarios. Dedicated reviewer test account with sample data if authentication is required, video walkthrough, valid privacy/terms/support site URLs, domain ownership verification (as the portal instructs), metadata checks.
5. **Submit:** verified OpenAI Platform business/developer identity; Plugins → Upload plugin ZIP → automated scans → review submission → approved → Publish. Public discovery and placement are NOT guaranteed.
6. **Measurement:** legitimate installs, opt-in connections, tool task-completion, error rates, repeat users, and independent site customer acquisition. No undisclosed profiling. Measure public-integration costs and user satisfaction before launching more tools.

## Free vs paid account behaviour (compliant)
A plugin delivers useful capabilities in-chat even for users with no existing paid account. For connected Empire AI paid subscribers, authenticate against their existing account and enforce existing entitlements. For a blocked feature: neutral explanation of entitlement and optional informational plan page only. No purchase prompts, subscription comparisons in listing, free-trial promotion, checkout link, or auto-upgrade. Keep customer billing wholly off the plugin interaction unless future documented rules explicitly authorize digital-goods commerce.

## Next founder action
1. Use https://platform.openai.com to confirm developer organisation identity and verification.
2. Choose the eventual customer-facing branded plugin name and supplied company privacy/contact/support information.
3. Authorize only a narrow consumer-facing MCP route after private account isolation, auth and API quota tests PASS; don't open the internal ops MCP.

**Status at authoring:** Planning/documentation only; no plugin published/submitted, no external customer MCP route created, no purchase transaction configured.
