# Empire OS — 6-Month Revenue Blitz (Rebuild from 2026-07-26 roadmap)

Goal: turn the existing lead engine (29k+ qualified B2B leads, 918 buyers registered,
working lead-gen + enricher + waterfall + lead scoring + ICP + ingest) into REAL settled
revenue on BSC USDT (vault 0x1339b487046B0ad924a10c20b1791608EA8595a8).

Root cause of $0 to date:
- Buyer portal was never publicly payable (app.empire-ai.co.uk pointed at Omega, not Empire OS).
  FIXED 2026-08-19: app.empire-ai.co.uk -> :8000 (Empire OS buyer portal).
- si_products table empty + schema drift (setup_fee_usdc missing) broke /v1/products/pricing.
  Migration in progress (Manus) — adds setup_fee_usdc/features/benefits/deliverables, seeds 20+ SKUs.
- A2A MCP server (empire_mcp.py :8082) was DOWN (FastMCP API break). FIXED 2026-08-19, running via systemd.

## Product Tiers (pricing model)
Charges in USDT on BSC. No contract, no monthly minimum.

1. LeadFlow (per-lead marketplace seat)
   - T1 $497 / mo — 25 exclusive leads/mo, scored + ICP-matched
   - T2 $1,247 / mo — 75 leads/mo + waterfall priority
   - T3 $2,497 / mo — 200 leads/mo + dedicated lane + CRM sync
   - T4 Titanium $4,997 / mo — unlimited vertical lane + white-label

2. ICO / Capital Raise Track
   - Entry $2,999 — investor lead pack (accredited B2B)
   - Scale $9,999 — full raise funnel + outreach agent

3. v4 Enterprise Intelligence
   - $9,999 setup + $4,997/mo — predictive revenue engine, cortex scores, A2A commerce

## 6-Month Phase Plan
Month 1 (Aug): STOP THE BLEED
- Buyer portal payable (done routing). Seed si_products. Verify GET /v1/products/pricing 200.
- Email 918 registered buyers with REAL pay path: vault address + amount + portal link (no placeholders).
- Launch 1 proof lane (e.g. HVAC / DEN): 50 leads -> first settled USDT.

Month 2 (Sep): CONVERT THE 29k
- Run enricher + waterfall + lead_scoring + ICP on backlog. Score all 29k, tier A/B/C.
- Outreach agent (a2a_sales_agent) to A-tier. Inbound to portal.
- Target: $10k settled.

Month 3 (Oct): A2A COMMERCE LIVE
- empire_mcp.py (now up :8082) exposed to buyer agents. list_open_lanes / quote_lane / buy_leads.
- AEO pages (3,854) cite empire_stats -> LLM-driven buyer traffic.
- Target: $25k settled.

Month 4 (Nov): SCALE LANES
- Open 10+ vertical lanes. seat_corridors + lane_router active.
- Media buyer + ppc_router drive paid traffic to portal.
- Target: $50k settled.

Month 5 (Dec): WHITELABEL + ENTERPRISE
- T4 Titanium white-label for agencies. v4 intelligence upsell.
- Target: $100k settled.

Month 6 (Jan): COMPOUND
- Recurring T1-T4 seats + A2A agent volume.
- Target: $180k cumulative (original projection).

## What Market Needs (validated)
Businesses want to BUY exclusive, scored, ICP-matched leads with crypto or card,
no contract. We have the supply (29k leads) + the engine. The missing piece was a
public, payable surface + working settlement. Now fixed at the routing + MCP layer.

## Services That Must Stay Running (survive laptop shutdown)
Host (Vultr 216.128.149.56): caddy, cloudflared, omega-ai-production, empire-orchestrator,
  lead-deliverer, lane-monitor, ppl-service, north-mini, mesh
Container empire-hub: hub (8081), empire-mcp (8082) [FIXED], bsc-listener, lanes, mail-sender
External: listmonk (email), twenty (CRM), pinecone-mcp (vector), posthog (analytics)

## Blockers Resolved This Session (2026-08-19)
- app.empire-ai.co.uk repointed to Empire OS portal (:8000)
- empire_mcp.py fixed (FastMCP API) + running on :8082 via systemd
- si_products pricing migration scoped (Manus applying)
- Vultr empireops SSH access enabled for external ops

## Next
1. Confirm si_products seeded + /v1/products/pricing 200 (Manus).
2. Send buyer email blast with pay path.
3. Open proof lane, collect first USDT.
