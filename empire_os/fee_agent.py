"""
Fee Agent — computes platform fees on each settled deal.

Empire OS takes a cut of every settlement (configurable). Two modes:
- "flat": fixed percentage of every settlement
- "tiered": percentage decreases as monthly volume grows

Fee amounts are stored alongside settlements and a payout is split
into two parts: client_payout + empire_fee.

Example:
  Settlement: $5,000
  Fee rate: 15% (tiered tier 1)
  Client payout: $4,250
  Empire fee:    $750
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fee_agent")


@dataclass
class FeeTier:
    """Volume-based pricing tier."""
    min_monthly_volume_cents: int = 0
    fee_basis_points: int = 1500       # 15.00%


DEFAULT_TIERS = [
    FeeTier(0,         1000),   # < $10k/mo: 10%
    FeeTier(1000000,    800),   # $10k-$50k/mo: 8%
    FeeTier(5000000,    650),   # $50k-$100k/mo: 6.5%
    FeeTier(10000000,   500),   # $100k+/mo: 5%
]


class FeeAgent:
    """Computes platform fees and splits payouts."""

    def __init__(self, tiers: Optional[list] = None, flat_bps: Optional[int] = None):
        self.tiers = sorted(tiers or DEFAULT_TIERS, key=lambda t: t.min_monthly_volume_cents)
        self.flat_bps = flat_bps  # if set, ignore tiers and use flat rate
        self.records = []
        self.monthly_volume_cents = 0
        self.month_reset_at = datetime.now(timezone.utc).replace(day=1).isoformat()

    def calculate(self, amount_cents: int) -> dict:
        """Compute client_payout + empire_fee for a settlement.

        Returns dict with fee_bps, fee_cents, client_cents.
        """
        # Reset monthly volume at month boundary
        now = datetime.now(timezone.utc)
        if now.month != datetime.fromisoformat(self.month_reset_at).month:
            self.monthly_volume_cents = 0
            self.month_reset_at = now.replace(day=1).isoformat()

        if self.flat_bps is not None:
            fee_bps = self.flat_bps
        else:
            fee_bps = 0
            for tier in reversed(self.tiers):
                if self.monthly_volume_cents >= tier.min_monthly_volume_cents:
                    fee_bps = tier.fee_basis_points
                    break
            if fee_bps == 0 and self.tiers:
                fee_bps = self.tiers[0].fee_basis_points

        fee_cents = int(amount_cents * fee_bps / 10000)
        client_cents = amount_cents - fee_cents

        self.monthly_volume_cents += amount_cents

        return {
            "gross_cents": amount_cents,
            "fee_bps": fee_bps,
            "fee_cents": fee_cents,
            "client_cents": client_cents,
            "monthly_volume_cents": self.monthly_volume_cents,
        }

    def record(self, settlement_id: str, amount_cents: int) -> dict:
        split = self.calculate(amount_cents)
        entry = {
            "settlement_id": settlement_id,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            **split,
        }
        self.records.append(entry)
        logger.info("fee: gross $%.2f, fee $%.2f (%d bps), client $%.2f",
                   amount_cents / 100, split["fee_cents"] / 100,
                   split["fee_bps"], split["client_cents"] / 100)
        return entry

    def observe(self) -> dict:
        total_fee = sum(r["fee_cents"] for r in self.records)
        total_client = sum(r["client_cents"] for r in self.records)
        return {
            "agent": "fee-agent",
            "settlements_processed": len(self.records),
            "total_gross_cents": sum(r["gross_cents"] for r in self.records),
            "total_fee_cents": total_fee,
            "total_client_cents": total_client,
            "monthly_volume_cents": self.monthly_volume_cents,
        }

    def reason(self, state: dict) -> str:
        return json.dumps({"action": "compute_fee", "reasoning": "settlement requires split"})

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except json.JSONDecodeError:
            d = {"action": "skip"}
        if d.get("action") == "compute_fee":
            amount = d.get("amount_cents", 0)
            sid = d.get("settlement_id", "")
            if amount and sid:
                split = self.record(sid, amount)
                return {"action": "compute_fee", "split": split}
        return {"action": "skip", "summary": "no fee computation"}