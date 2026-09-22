# Phase 4 — Commercial Exchange

Status: **CURRENT**

Phase 3F is closed at the engineering and production-automation level with real
outcome evidence dependencies carried forward. Phase 4 now converts qualified
opportunities into governed Empire-owned commercial inventory.

## Canonical flow

**Acquire → Qualify → Inventory → Lane → Corridor → Buyer Seat → Capacity →
Allocation Proposal → Allocated or Overflow**

Acquisition never stops because a buyer seat is full.

## Canonical entities

### Lane
A commercial grouping of compatible corridors. A lane is organizational; it
does not by itself create price, exclusivity or buyer capacity.

### Corridor
A deterministic commercial route:

**niche/product × territory × demand type × delivery type**

### Buyer Seat
A governed buyer right/capacity inside one corridor. Activation requires:
- verified buyer identity;
- verified commercial terms;
- verified capacity;
- verified delivery destination;
- verified territory eligibility;
- explicit exclusivity evidence when exclusivity is claimed.

### Qualified Inventory
Empire-owned opportunities that passed canonical qualification and identity
evidence gates.

### Overflow Inventory
Qualified Empire-owned opportunities that cannot currently be delivered because
no eligible verified buyer capacity exists.

Overflow remains owned by Empire and may be routed later to:
- another buyer;
- another corridor;
- a governed marketplace/feed;
- nurture;
- reserved/future capacity.

## Existing canonical foundations

Use and extend:
- `public.prospects`;
- `public.prospect_qualifications`;
- `public.prospect_entity_links`;
- `public.gtm_opportunities`;
- `public.buyers`;
- `public.buyer_commercial_evidence`;
- `public.buyer_capacity_intakes`;
- `public.buyer_subscriptions`;
- `public.fulfilment_orders`;
- `empire_os/buyer_allocation.py`;
- `empire_os/buyer_capacity_readiness.py`;
- `empire_os/revenue_exchange*.py`;
- atomic allocation migration already present in the repo.

Legacy/reference-only:
- `empire_os/lanes.py`;
- `empire_os/seat_corridors.py`;
- old SQLite lane occupancy;
- historical lane pricing;
- legacy settlement assumptions.

Do not restore those as production truth.

## Build order

1. **Exchange schema contract**
   - canonical exchange lanes;
   - corridors;
   - buyer seats;
   - qualified inventory;
   - overflow inventory;
   - immutable/auditable evidence references.

2. **Inventory materializer**
   - consume only real canonical qualified prospects/opportunities;
   - never fabricate supply;
   - keep acquisition independent of buyer capacity.

3. **Seat/corridor readiness**
   - verified commercial terms;
   - verified capacity;
   - delivery route;
   - territory;
   - exclusivity;
   - pricing evidence.

4. **Deterministic allocation proposal**
   - fail closed on missing evidence;
   - rank eligible seats;
   - do not silently accept terms or send inventory externally.

5. **Overflow routing**
   - persist Empire-owned unallocated inventory;
   - re-evaluate automatically as capacity changes;
   - support alternate corridors/buyers and future marketplace/feed routes.

6. **Automation**
   - recurring inventory refresh;
   - recurring buyer-capacity refresh;
   - recurring seat/corridor readiness refresh;
   - recurring allocation-proposal refresh;
   - recurring overflow re-evaluation;
   - Founder Console status.

7. **Upgrade & Enhance**
   - margin-aware routing;
   - dynamic price recommendation from verified evidence only;
   - reserved future capacity;
   - demand pre-selling;
   - territory/exclusivity premiums.

8. **Revenue Expansion**
   - buyer-seat subscriptions;
   - corridor subscriptions;
   - usage/overage economics;
   - overflow monetisation;
   - marketplace/feed products.

9. **Re-test and close Phase 4**
   - a real qualified opportunity can enter inventory;
   - allocation is deterministic/auditable;
   - full buyer capacity produces overflow, not acquisition shutdown;
   - no invented identity, terms, price, capacity or revenue.

## Authority

Phase 4 remains OBSERVE/internal-write for automated internal state and
proposals. External delivery, binding commercial terms, fund movement, payment
confirmation and revenue recognition remain separately governed.

## Security gate

The live Supabase project currently reports public tables with RLS disabled,
including commercial tables. Do not blanket-enable RLS without matching
policies because that can break production access. Audit the Commercial
Exchange tables and define least-privilege policies before exposing new Phase 4
objects through the Data API.
