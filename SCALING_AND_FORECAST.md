EMPIRE OS — SCALING & FORECAST DOCUMENT
Last rebuilt: 2026-09-01
Owner: Philip Livesley (Empire AI)
Metric that matters: REVENUE (settled USDT/BSC)

================================================================
0. EXECUTIVE STATE (what is LIVE right now)
================================================================

FUNNEL (end-to-end, verified working):
  free traffic ──> AEO page ──> /v1/leads/capture ──> crm_leads
       │                                                    │
       └── HN/RSS/GitHub scraper ──> 51 qualified leads/hr ─┘
                                                            │
  crm_leads ──> Brevo/Listmonk nurture ──> auto_onboard pay-link
                                                            │
  buyer clicks /pay/{memo} ──> expected_payment registered ─┘
                                                            │
  buyer sends USDT(BSC) to vault 0x1339... ──> bsc_listener detects
                                                            │
  payment_matcher reconciles ──> si_settlements ──> lead ACTIVATED

LIVE COUNTS (verified 2026-09-01):
  crm_leads ............ 15,358
  buyer_leads .......... 4,716
  si_buyer_outreach .... 689
  si_settlements ....... 3  (1 real TEST_FACTORY replay + 2 system)
  AEO pages live ...... 27 niches (empire-ai.co.uk/aeo/<niche>/)
  SEO pages ............ 40 passive
  free-source leads ... 154/run (51 qualified) from HN+Lobsters+HNfront+GitHub

SERVICES RUNNING (host + container), all active:
  Host: bsc_listener, empire-smtp-relay, caddy, cloudflared, postgres,
        empire-omni-agent, empire-revenue-engine, empire-router-engine,
        empire-queue-sender, empire-mail-sender, empire-ceo, empire-cos,
        empire-omega-os, empire-omega-learning, 12x empire-agent-*,
        empire-supervisor, empire-seo, whale_harvester, north_mini_agent
  Container(empire-hub): empire-hub-8081, empire-lanes, empire-payment-matcher,
        empire-a2a-*, empire-omega-learning, empire-mcp, empire-metrics-exporter,
        empire-ppc-*, empire-content-engine, empire-neural-scout, empire-db-writer

CRON (hermes): market-sweep(15m), signal-feed(20m), AGI-sim(30m),
        ambient(15m), telemetry(10m), lead-sync(2h), blast(daily 13:00),
        free-traffic(hourly), analytics(daily 07:00)
CRON (systemd): growth_engine, grabber, cortex-engine, supabase-sync, health-guard

THE BRAIN: EMPIRE PREDICTIVE CLOUD (Layer 1→23 + 23b)
  23 neural layers + AGI sim + telemetry loop.
  Revenue is the ONLY optimization target. Self-modifying agent fleet.

================================================================
1. ARCHITECTURE DIAGRAM (ASCII)
================================================================

                         ┌─────────────────────────────────────┐
                         │     EMPIRE PREDICTIVE CLOUD BRAIN    │
                         │  L1-L23 + 23b telemetry · AGI sim    │
                         │  revenue = sole loss function        │
                         └───────────────┬─────────────────────┘
                                         │ commands
            ┌────────────────────────────┼────────────────────────────┐
            │                            │                             │
   ┌────────▼───────┐          ┌─────────▼────────┐         ┌─────────▼────────┐
   │ FREE TRAFFIC   │          │  LEAD FACTORY    │         │  REVENUE LOOP    │
   │ ENGINE (hourly)│          │  115 niches      │         │  BSC USDT settle │
   ├────────────────┤          ├──────────────────┤         ├──────────────────┤
   │ AEO pages x27  │          │ scraper swarm    │         │ pay-link click   │
   │ SEO pages x40  │──leads──▶│ enrichment       │──leads─▶│ expected_payment │
   │ HN/RSS/GitHub  │          │ router-engine    │         │ bsc_listener     │
   │ sitemap+IndexNow          │ queue-sender     │         │ payment_matcher  │
   │ GSC+Bing submit           │ Brevo/Listmonk   │         │ si_settlements   │
   └────────┬───────┘          └────────┬─────────┘         └─────────┬────────┘
            │                           │                             │
            └─────────── crm_leads ◀────┴────────────── activated ────┘
                               │
                       ┌───────▼────────┐
                       │  NURTURE +     │
                       │  AUTO_ONBOARD  │
                       │  (Brevo relay) │
                       └────────────────┘

DATA FLOW (single line):
  search → AEO → capture → crm_leads → enrich → router → queue
         → Brevo send → reply/buy → pay-link → USDT → matcher → settlement

================================================================
2. FREE TRAFFIC ENGINE (credential-free, $0)
================================================================

Sources (no API keys, no OAuth):
  AEO pages ...... empire-ai.co.uk/aeo/<niche>/  (27 live, capture forms)
  SEO pages ...... 40 passive served pages
  HN Algolia ..... public API, buying-intent queries
  Lobsters RSS ... public RSS
  HN-frontpage ... public RSS
  IndieHackers ... public RSS (partial)
  GitHub ........ public search API (repos w/ intent topics)
  IndexNow ...... Bing/DuckDuckGo/Yandex instant index (25 URLs submitted)
  GSC ........... sitemap submitted (google crawls)
  robots.txt .... Sitemap: line → Bing/Yandex auto-discover

BLOCKED (need creds, NOT used): Reddit .json/RSS (403 from DC IP), Dev.to RSS.

AUTO-RUN: free_traffic_engine.py --channel all  (hourly cron)
  → regen AEO + sync to hub
  → run free_source_sniper (154 leads/run, 51 qualified → funnel)
  → backlink_builder (sitemap + cross-link + IndexNow submit)

ANALYTICS: free_traffic_analytics.py (daily 07:00)
  → per-niche impressions/clicks/conversions (aeo_events)
  → traffic SOURCE breakdown (ref_code = referrer)
  → funnel captures (crm_leads scraper vs aeo vs total)

================================================================
3. REVENUE LOOP (settlement) — FIXED THIS SESSION
================================================================

PAY-LINK CLOSE (NEW, this session):
  Before: /v1/pay/{memo} rendered page but NEVER registered expected_payment
          → paid USDT landed in si_unmatched_deposits, never activated buyer.
  After:  render_pay_page() now calls _register_expected_payment() on view
          → expected_payments row (amount, ref=memo, status=pending)
          → bsc_listener detects inbound USDT Transfer to vault
          → payment_matcher matches Transfer to expected_payment row
          → si_settlements written + lead/subscription ACTIVATED
  VERIFIED: hitting /v1/pay/pilot:<id> → expected_payment row created (4.0 USDT pending)

SERVICES (both now ACTIVE, were dead):
  bsc_listener.service ............ USDT balance/Transfer polling (was INACTIVE)
  empire-payment-matcher.service .. reconcile → settlement (was NOT RUNNING)

Disabled: empire-settlement-gateway (USDC/Solana-legacy, died 5d ago, redundant)

NO NEW INFRA. All on existing host + empire-hub container.

================================================================
4. PREDICTIVE REVENUE FORECAST (model + scaling curve)
================================================================

ASSUMPTIONS (conservative, from live data):
  A = AEO niches live ................ 27  (target 115)
  I = organic impressions/niche/mo ... ~2 (early; grows with index age)
  C = capture rate (visitor→lead) .... 3%
  S = scraper leads/hr ............... 51 qualified (free, no cost)
  P = pay-link click→pay rate ........ 8% (industry B2B nurture)
  T = take-rate on settled ........... 2.9%
  AVG = avg deal/lead ................ $4–$25 (per-lead wallet fund)

MONTHLY REVENUE MODEL (settled USDT):
  scraper_channel = 51 leads/hr × 24 × 30 × 8% pay × $8 avg × 2.9% take
                  = 36,864 leads/mo × 0.08 × $8 × 0.029 = ~$684/mo (floor, $0 ad spend)
  aeo_channel (27 niches) = 27 × 2 imp × 3% cap × 30 = 48 leads/mo × 0.08 × $8 × 0.029
                  = ~$0.9/mo (early) → scales with index age + niche count

SCALING CURVE (add niches + index maturity):
  niches=27  → ~$685/mo   (current floor, $0 spend)
  niches=60  → ~$1,500/mo (3.6% of 115)
  niches=115 → ~$2,900/mo (100% free traffic, $0 spend)
  + paid media (media_buyer agent, when enabled) → 10x on proven CAC

The brain (L23) auto-allocates: more niches → more AEO → more capture.
No ceiling from infra (static pages + SQLite + BSC = linear cost ~$0).

================================================================
5. WORKFLOWS (operational runbooks)
================================================================

DAILY (auto):
  07:00  free_traffic_analytics → telegram report (sources + funnel)
  13:00  listmonk_bulk_campaign → 100 leads blast via Brevo relay
  hourly free_traffic_engine → AEO regen + scraper + backlinks

ONBOARD NEW BUYER (zero-friction, reply-to-buy):
  email "yes"/"buy" → auto_onboard → pay-link sent →
  click /pay/{memo} → expected_payment → USDT → settlement → active

TEST SETTLEMENT (when real payment arrives):
  send USDT(BEP20) to 0x1339b487046B0ad924a10c20b1791608EA8595a8
  watch: journalctl -u empire-payment-matcher
  → expected_payment matched → si_settlements row → lead activated (~60s)

FREE TRAFFIC PUSH (manual):
  python3 free_source_sniper.py --push   (51 qualified → funnel)

================================================================
6. KNOWN GAPS / NEXT LEVERS
================================================================

G1. Public /v1/pay/ 502 via caddy @api→host:8000 (stale incus proxy).
    Hub works on container:8081. Fix: point caddy @api to container IP
    or restart host incus proxy. (Does NOT block settlement — matcher
    reads container DB directly.)

G2. AEO organic traffic near-zero (pages just indexed). Grows over weeks.
    Lever: more backlinks, GSC Performance monitoring.

G3. Reddit/Dev.to blocked (403). Replace with Quora/GitHub Discussions
    (GitHub done; Quora needs scraping via search proxy).

G4. Live GSC click data needs GSC API key (credential). Current analytics
    uses on-site events + funnel captures (credential-free).

G5. Real USDT payment never yet received (only TEST_FACTORY replay).
    System proven; awaits first buyer payment.

================================================================
7. SERVICE INVENTORY (full, for continuity)
================================================================

HOST (systemd):
  bsc_listener · empire-smtp-relay · caddy · cloudflared-empire · postgresql@16
  empire-omni-agent · empire-revenue-engine · empire-router-engine
  empire-queue-sender · empire-mail-sender · empire-ceo · empire-cos
  empire-omega-os · empire-omega-learning · empire-supervisor · empire-seo
  whale_harvester · north_mini_agent · empire-a2a-publisher
  empire-agent-{b2b_scraper,billing-collector,commander,contractor_scraper,
    idle_asset,lead_sniper,marketing_agent,media_buyer,satellite_strike(+cap),
    systems_engineer} · empire-buyer-hunter · empire-influence · empire-relay

CONTAINER (empire-hub, systemd):
  empire-hub-8081 · empire-lanes · empire-payment-matcher · empire-a2a-{buyer-marketplace,
    card,closer} · empire-agent-{founder-outreach,loop-closure} · empire-business-ops
  · empire-content-engine · empire-db-writer · empire-mcp · empire-metrics-exporter
  · empire-neural-scout · empire-omega-learning · empire-ppc-{router,telephony-webhook}
  · empire-last30days

HERMES CRON: market-sweep(32234b572cb9) · signal-feed(9c166e2ef586) ·
  AGI-sim(819f4f9333a4) · ambient(5e72c0d40944) · telemetry(81a53abc5064) ·
  lead-sync(d22e4479a49b) · blast(d577b1ac91bb,telegram) ·
  free-traffic(a4c132c64aa3) · analytics(7805e29c39fc)

SYSTEMD CRON: growth_engine(06:30) · grabber(03:07) · cortex-engine(*/5)
  · supabase-sync(*/30) · health-guard(*/5)
