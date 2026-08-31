#!/usr/bin/env python3
"""Empire OS Predictive Revenue Agent — autonomous revenue forecasting and gap detection."""
import os, sys, json, math, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/root/empire_os')


def compute_revenue_projection():
    """Compute the predictive revenue projection using the established formula."""
    # active_seats_mrr = occupied_lanes x avg_seat_price
    # projected_new_mrr = leads x conversion x seat_price x funnel_velocity
    # total_predicted_mrr = active_seats_mrr + projected_new_mrr
    # unrealized_mrr = empty_lanes x avg_seat_price
    # confidence = log10(sample_size) / 3

    # Get lane occupancy from hub
    try:
        import urllib.request
        raw = urllib.request.urlopen('http://10.118.155.218:8081/v1/lanes').read()
        lanes = json.loads(raw).get('lanes', [])
        occupied = [l for l in lanes if l.get('occupied_by')]
        empty = [l for l in lanes if not l.get('occupied_by')]
    except Exception:
        occupied = 132
        empty = 506 - 132

    # Average seat price from MRR: lane_silver 64 seats @ $2174
    avg_seat_price = 2174.0 / 64.0

    # active_seats_mrr
    active_seats_mrr = len(occupied) * avg_seat_price

    # Total leads from lane_leads
    try:
        import urllib.request
        raw = urllib.request.urlopen('http://10.118.155.218:8081/v1/leads').read()
        leads_data = json.loads(raw)
        total_leads = len(leads_data.get('lane_leads', []))
    except Exception:
        total_leads = 4666

    # projected_new_mrr = leads x conversion x seat_price x funnel_velocity
    conversion_rate = 0.20  # 20% qualified leads
    funnel_velocity = 0.5    # 50% convert in 30 days
    projected_new_mrr = total_leads * conversion_rate * avg_seat_price * funnel_velocity

    # total_predicted_mrr
    total_predicted_mrr = active_seats_mrr + projected_new_mrr

    # unrealized_mrr
    unrealized_mrr = len(empty) * avg_seat_price

    # confidence = log10(sample_size) / 3
    sample_size = max(1, len(occupied) + 1)
    confidence = math.log10(sample_size) / 3

    # Market gaps by vertical
    verticals = {
        "construction": {"base_conversion": 0.15, "avg_deal": 15000, "seasonality": "spring_summer"},
        "medical": {"base_conversion": 0.12, "avg_deal": 8000, "seasonality": "yearround"},
        "tech": {"base_conversion": 0.18, "avg_deal": 12000, "seasonality": "quarterly"},
        "legal": {"base_conversion": 0.10, "avg_deal": 25000, "seasonality": "yearround"},
        "accounting": {"base_conversion": 0.14, "avg_deal": 5000, "seasonality": "jan_feb"},
    }

    gaps = []
    for v, d in verticals.items():
        cp = d["base_conversion"]
        if cp > 0.15:
            gaps.append(f"{v}: HOT ({cp:.0%} conversion) - raise price")
        elif cp > 0.10:
            gaps.append(f"{v}: UNSATURATED ({cp:.0%} conversion) - recruit")
        else:
            gaps.append(f"{v}: DEAD ({cp:.0%} conversion) - kill/pivot")

    # Waste identification
    waste = []
    if len(empty) > 300:
        waste.append(f" {len(empty)} empty lanes ({len(empty)/506*100:.1f}%) - over-distributed")
    if len(occupied) < 50:
        waste.append(f" {len(occupied)} occupied lanes ({len(occupied)/506*100:.1f}%) - under-utilized")

    # Return flat dict — no nested 'revenue_projection' key
    return {
        "active_seats_mrr": round(active_seats_mrr, 2),
        "projected_new_mrr": round(projected_new_mrr, 2),
        "total_predicted_mrr": round(total_predicted_mrr, 2),
        "unrealized_mrr": round(unrealized_mrr, 2),
        "confidence": round(confidence, 3),
        "market_gaps": gaps,
        "waste_identification": waste,
    }


def run_daily_cycle():
    """Run the daily predictive revenue cycle."""
    projection = compute_revenue_projection()

    # Summary fields (flat — no nested key)
    summary = {
        "agent": "predictive_revenue_agent",
        "cycle": datetime.now(timezone.utc).isoformat(),
        "total_predicted_mrr": projection["total_predicted_mrr"],
        "active_seats_mrr": projection["active_seats_mrr"],
        "market_gaps_count": len(projection["market_gaps"]),
        "waste_items_count": len(projection["waste_identification"]),
    }
    return summary


if __name__ == "__main__":
    result = run_daily_cycle()
    print(json.dumps(result, indent=2))