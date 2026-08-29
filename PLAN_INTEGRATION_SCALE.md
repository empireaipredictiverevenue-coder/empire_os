# Empire OS — Full Integration + Scale Plan

Date: 2026-08-28. Author: senior-architect pass.
Scope: wire orphaned modules into live hub, build analytics, overhaul email, integrate
satellite products + agents, scale revenue loop. Revenue = only metric.

## CURRENT REAL STATE (verified)
- Hub live: container `empire-hub` @ 10.118.155.218:8081, single instance, health ok.
- Vault: 0x1339b487046B0ad924a10c20b1791608EA8595a8 (USDT 0.009). Real revenue = $0.00 (only test/replay rows in si_settlements).
- Orphaned modules (exist, NOT imported by hub.py): a2a_marketplace, a2a_closer,
  aeo_surface, pinecone_client, empire_mcp, si_mcp_bridge, neural_scout, web2a2a_agent,
  audit_api, deep_audit, hourly_retainer, evaluation_product(imported but unused),
  state_contractor_portals.
- Agents built: 50+ files. Running: ~14 (billing_collector, lead_sniper, marketing,
  media_buyer, mesh, satellite_strike x2, bsc_listener, commander, supervisor,
  whale_harvester, idle_asset_sniper, b2b_scraper, contractor_scraper, systems_engineer,
  code_review). NOT running: agi-scout, agi-marketing, seo-agent, lead-filter, reddit-sniper,
  scheduling, copywriting, email, predictive, growth, business, engineering.
- Analytics: NO click/reply/open/unsub tables. hub.py:730 references lead_clicks but table absent.
- Permit: lead_sources/permits.py + scripts/permit_monetize.py exist (source, not product API).

---

## EMAIL BACKEND (HARD CONSTRAINT)
- NEVER use SendGrid. Outbound = Brevo (EMAIL_BACKEND=brevo in /root/empire_os/.env +
  /root/empire_secrets/llm.env). From: Empire OS <founder@empire-ai.co.uk>.
- Resend key present but BLOCKED by Cloudflare (1010) + not selected as backend. Do not switch.
- All new email code routes through si_outbox → mail_sender (Brevo). No direct SMTP.

## PHASE 0 — EMAIL OVERHAUL (prereq for all outreach revenue)
P0.1 Build branded HTML email templates.
  - File: /root/empire_os/empire_os/templates/email/brand.py (exists, extend)
  - Add: EMAIL_HTML_WRAPPER(bg=#050810, accent=#39ff88, cyan=#22e3ff, footer w/ unsub+addr)
  - Relationship-first copy blocks per avenue (leadgen/paypercall/saas).
  - Verify: render 1 sample, check no raw bscscan URL in body.
P0.2 Separate payment page (no pay link in body).
  - Add hub route GET /pay/{memo} → branded landing: vault QR + BSC pay button + amount.
  - File: /root/empire_os/empire_os/hub.py (new route ~line 7300)
  - Email body links to https://empire-ai.co.uk/pay/{memo} only.
  - Verify: curl /pay/{test_memo} returns 200 HTML.
P0.3 Link shortener + cloaker.
  - Add hub route GET /r/{token} → log lead_clicks + 302 to real URL.
  - Table link_redirects(token, target, created_at).
  - All email links go through /r/. Verify: curl -I /r/x → 302 Location=target.
P0.4 Anti-spam + opt-out compliance.
  - From: verified founder@empire-ai.co.uk (Brevo). Add List-Unsubscribe header.
  - Route GET /unsub?email= → mark si_outbox recipient suppressed + si_buyer_outreach.
  - Mail-merge spintax to dodge filters. Verify: send test, check headers + unsub works.
P0.5 Rewrite pilot + campaign emails (relationship-first).
  - /tmp/enterprise_pilot_activate.py → new body (no hard ask, link to /pay, /r links).
  - a2a_closer._send_pay_url → use branded wrapper, link to /pay/{memo}.
  - Verify: 1 sent email renders branded, no vault addr in body.

## PHASE 1 — ANALYTICS (click/reply/retarget)
P1.1 Create tables: lead_clicks(token,email,url,ip,ua,clicked_at), email_events(
  id,email,event,ts,meta), replies(inbound_id,email,body,ts), unsubscribes(email,ts).
  - File: /root/empire_os/empire_os/db_schema_analytics.sql + run via sqlite3.
P1.2 Wire /r/{token} click log + open-pixel (1x1 img) in email wrapper → email_events.
P1.3 Inbound reply daemon already posts /v1/inbound/reply (hub:3377). Confirm IMAP poller
  (inbound_reply_daemon.py) running + writes replies table.
P1.4 Retargeting engine: agent that pulls clicked-not-paid + replied → enqueue follow-up
  via si_outbox. File: /root/empire_os/empire_os/agents/retarget_agent.py.
  - Verify: seed 1 clicked lead, run tick, confirm follow-up enqueued.

## PHASE 2 — INTEGRATE ORPHANED REVENUE MODULES
P2.1 A2A marketplace: import + mount routes in hub.py (a2a_marketplace, a2a_closer).
  - Verify: /v1/a2a/quotes returns real rows; pay_url → /pay/{memo}.
P2.2 Audit + revenue leak + waste: wire audit_api + deep_audit + predictive.leak/waste.
  - Add dashboard routes /v1/audit/deep (exists), /v1/leak, /v1/waste.
  - Verify: call returns leak list + waste list from live DB.
P2.3 Satellite products: satellite_scanner + satellite_service + satellite_strike_service →
  mount as priced product (per-scan USDT). Verify: /v1/satellite/quote.
P2.4 Permit product API: wrap lead_sources/permits.py into /v1/permit/quote (metro+niche →
  price). Verify: returns priced permit lead package.
P2.5 Evaluation product: evaluation_product.py imported (hub:10951+) — expose /v1/eval/product.
P2.6 Hourly payment system: hourly_retainer.py → /v1/retainer/start (USDT/hr, streamed).
P2.7 Self-serve lead portal: state_contractor_portals.py → /portal/{tenant} branded buyer view.
P2.8 AEO pages: aeo_surface + aeo_seed → auto-publish citeable asset pages; mount /aeo.

## PHASE 3 — AGENTS INTO EMPIRE OS
P3.1 Register all built agents in config/agent_registry.json (currently only version/agents/last_updated).
P3.2 Spin up missing containers via scripts/agent_registry.py create for: agi-scout,
  agi-marketing, seo-agent, lead-filter, reddit-sniper, scheduling, copywriting, email,
  predictive, growth, business, engineering.
P3.3 Neural scout market agent → wire into cortex_engine + a2a_buyer_marketplace feed.
P3.4 Pinecone: pinecone_client → vector memory for leads/buyers; hub import + /v1/memory.
P3.5 MCP: empire_mcp + si_mcp_bridge → expose tools to external agents; /v1/mcp.
P3.6 web2a2a_agent + own a2a agent → A2A settlement layer (already a2a_settle_bridge exists).

## PHASE 4 — SCALE
P4.1 Capacity: hub single-instance guard holds; add worker scaling via incus profile.
P4.2 Revenue loop: pilot pay-links (579 sent) → when USDT lands, lead_deliverer auto-streams.
P4.3 Outreach: 449 queued + campaign A/B via Brevo with analytics → retarget non-payers.
P4.4 Forecast: predictive.py daily → /v1/predictive/revenue (MRR projection, gaps, leaks, waste).
P4.5 Observability: cortex_engine + dashboard show real revenue (si_settlements truth), not phantom.

## SUCCESS INVARIANTS
- si_settlements = truthful revenue (only real on-chain USDT).
- No raw vault address in any email body. All links via /r/ + /pay/.
- Every agent registered + running or explicitly retired.
- Analytics tables populated; retargeting fires on click/reply.
