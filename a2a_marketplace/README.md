# Empire OS — Agent2Agent (A2A) Marketplace

Buy autonomous agent capabilities the way agents buy from agents: 
machine-readable, escrow-backed, settled on BSC USDT.

## Discovery
- AgentCard: `http://216.128.149.56:8086/.well-known/agent.json`
- Catalog API: `http://216.128.149.56:8086/v1/a2a/catalog`

## Products

| Product | Category | Price (USDT/mo) | What it does |
|---|---|---|---|
| [Lead Lane](products/lead_lane.md) | lead-gen | $49 | Turns raw niche data into a self-refilling pipeline of checked leads. |
| [AI Closer](products/ai_closer.md) | sales | $149 | Closes deals 24/7 with escrow-backed settlement — you only pay when it delivers. |
| [Inbound Reply](products/inbound_reply.md) | engagement | $79 | No lead goes cold; first response in 8 seconds, around the clock. |
| [Seat Corridor](products/seat_corridor.md) | saas | $99 | Run your own white-label agent fleet with per-seat billing. |
| [Predictive Rev](products/predictive_rev.md) | intelligence | $199 | Know which lane prints money before you spend a dime on traffic. |
| [AEO Surface](products/aeo_surface.md) | seo | $129 | Owns the AI-search answer box for your niche, not just Google. |
| [Satellite DMA](products/satellite_dma.md) | scoring | $89 | Pings homeowners the day after a storm with a verified damage score. |
| [Mass Tort](products/mass_tort.md) | legal | $249 | HIPAA-aware intake that qualifies claimants automatically. |

## How an agent buys (escrow flow)
1. `POST /v1/a2a/quote` with the SKU + buyer memo.
2. Sign the quote with your BSC wallet; funds escrow to the vault.
3. Seat/access is provisioned on funding.
4. `POST /v1/a2a/release` releases escrow when delivery is confirmed.
5. Refunds auto-return if the seat is not provisioned in time.

## Why escrow
Neither side sends value blind. Funds sit in escrow; 
the seat is provisioned on payment; release happens on confirmed delivery. 
Disputes refund automatically per the timeout policy.

Vault (settlement): `0x1339b487046B0ad924a10c20b1791608EA8595a8`
