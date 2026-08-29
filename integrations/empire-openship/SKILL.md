---
name: empire-openship
description: Empire OS wrapper around openshiporg/openship (order orchestration platform). Next.js 15 + KeystoneJS 6 — connects shops (order sources) with channels (fulfillment providers) through matching/routing. Wire into Empire OS as the "ops/shipping" tier for E-commerce lead customers.
license: MIT
---

# Empire OpenShip

Wire the OpenShip 4 repo (https://github.com/openshiporg/openship) — Next.js 15 +
KeystoneJS 6 order orchestration platform — into Empire OS as the fulfillment
backend for E-commerce / Shopify / WooCommerce lead customers.

## What it does

- Connects shops (order sources: Shopify, WooCommerce) with channels (fulfillment: Amazon, 3PL)
- Two-tier architecture: ShopPlatform/ChannelPlatform define capabilities, Shop/Channel are instances
- Order flow: Shop Order → Order → Matching → CartItem → Channel Fulfillment → Tracking → Shop Notification
- Automation modes: sequential (try in order) / simultaneous (broadcast all)
- 15+ KeystoneJS data models, full GraphQL API

## Empire OS revenue integration

For E-commerce / Shopify / Amazon niches, OpenShip becomes the **fulfillment layer**
Empire's lead-generation funnels drop into. Buyer chain:

1. Empire finds Shopify/Amazon merchant (lead generation)
2. Buyer signs up Empire starter plan → gets leads
3. Buyer uses OpenShip to fulfill orders from those leads
4. Cross-sell: Enterprise plan + OpenShip deployment + Webhook delivery

## Setup

Cloned at `/root/empire_os/integrations/openship/`.

### Local dev
```bash
cd /root/empire_os/integrations/openship
npm install
npm run dev   # keystone build + migrate + next dev
```

### Production build
```bash
npm run build
npm run start
```

## Empire OS hub integration

Two endpoints to add to hub.py:

```python
@app.post("/v1/openship/connect_shop")
def openship_connect_shop(req: ...):
    """Register a new shop (Shopify, Woo) with OpenShip."""

@app.post("/v1/openship/sync_orders")
def openship_sync_orders(req: ...):
    """Pull recent orders from a connected shop via OpenShip GraphQL."""
```

Or run OpenShip as a sidecar container alongside empire-hub:

```yaml
# /etc/systemd/system/empire-openship.service
[Service]
ExecStart=/root/hunt_venv/bin/npm --prefix /root/empire_os/integrations/openship run start
WorkingDirectory=/root/empire_os/integrations/openship
Environment=PORT=3000
```

## Empire OS lane activation

Activate empty lanes:
- shopify_merchant (N metros, $499/seat)
- amazon_seller (N metros, $499/seat)
- woocommerce_store (N metros, $299/seat)
- 3pl_fulfillment (N metros, $1,999/seat)

## Caveats

- Next.js 15 + KeystoneJS 6 — non-trivial to deploy standalone. Recommend running
  as a sidecar or per-buyer instance (not shared multi-tenant) for security.
- Heavy DB dependency (Prisma). Each buyer instance needs its own DB.