# EMPIRE OS — Full Integration & Scale Plan
## State (2026-08-28): modules exist as files, MOST ORPHANED (not mounted in hub, no analytics, no orchestration)

## PHASE 1 — REVENUE FOUNDATION (do first; everything depends on it)
- [ ] 1.1 Analytics backbone: click/reply tracking tables + /r/<id> cloaked short-link redirect (logs to lead_clicks)
- [ ] 1.2 Retargeting engine: score by clicked/opened/replied → segment hot/warm/cold → auto-resend cadence
- [ ] 1.3 Branded HTML email templates (dark/neon-green/cyan per brand.py) — relationship-first, NO pay link in body
- [ ] 1.4 Separate /pay/<memo> branded payment page (QR + BSC button); email links to it, body stays value copy
- [ ] 1.5 Anti-spam: List-Unsubscribe header + /unsub page + plaintext alt + from reputation (founder@empire-ai.co.uk)
- [ ] 1.6 Short-link cloak: all external links → empire-ai.co.uk/r/<id> (professional, trackable)
- [ ] 1.7 Rewrite pilot + Campaign A/B emails using above; verify in outbox before send

## PHASE 2 — PRODUCT INTEGRATION (mount orphaned modules into hub)
- [ ] 2.1 audit_api.py + audit_report.py → /api/audit (revpath + leak + waste)
- [ ] 2.2 revenue leak/waste detector → /api/leak /api/waste (feeds OKF + retargeting)
- [ ] 2.3 permit product API → /api/permit
- [ ] 2.4 evaluation product → /api/evaluate
- [ ] 2.5 hourly_retainer.py → /api/hourly (hourly payment system)
- [ ] 2.6 state_contractor_portals.py + select_serve_router → self-serve lead portal (live)
- [ ] 2.7 satellite_service / storm_service / storm_predictor → satellite product API

## PHASE 3 — AGENT FLEET INCORPORATION
- [ ] 3.1 neural_scout.py + agi_scout.py → mounted as live agents (tick hooks in supervisor/orchestrator)
- [ ] 3.2 all built agents → registered in agent_registry + health URLs + liveness in supervisor
- [ ] 3.3 pinecone_client/intel → vector memory for scout + retargeting
- [ ] 3.4 empire_mcp.py + si_mcp_bridge.py + mcp_status_dashboard → MCP layer live
- [ ] 3.5 web2a2a_agent.py → A2A web agent live
- [ ] 3.6 a2a_* suite + aeo_* suite → mounted + cross-wired (A2A buyer marketplace + AEO pages)

## PHASE 4 — SCALE
- [ ] 4.1 Cash-filter buyer tool: score buyers by real cash (paid subs, funded quotes, on-chain balance, wallet age) vs lookie-loos
- [ ] 4.2 Multi-vertical avenues (brand.py AVENUES) per product
- [ ] 4.3 OKF + predictive regenerated from live integrated state
- [ ] 4.4 Capacity: container autoscale per agent, busy_timeout hardened

## REALITY CHECK (from live DB 2026-08-28)
- real revenue = $0.00 USDT from buyers (si_settlements = test/replay only)
- $13.80 snapshot was phantom (a2a 'released' flag, no on-chain proof)
- vault on-chain: 0.0090423 USDT
- 579 pilot emails sent, 0 replies, 0 paid → emails need work (Phase 1.3/1.7)
- host hub killed+masked; container single instance green
