"""
Process All Pending Payouts — one-call settlement.

Walks all pending payouts in the store, and for each one:
  - Builds a crypto payment request (or PayPal order, if method=paypal)
  - Bundles them into a single response so the operator can sign once
  - Returns a single batch ID + per-payout deeplinks

Operator flow:
  1. POST /v1/payouts/process-all
  2. Receive batch with N payment requests (each a USDC transfer deeplink)
  3. Open first deeplink in TokenPocket → approve
  4. Submit TX signature back via POST /v1/payouts/verify/{id}
  5. Repeat for each payout
  6. Dashboard updates show "paid" as each is verified
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("payout_batch")


@dataclass
class PayoutBatch:
    """A batch of payment requests queued for operator approval."""
    batch_id: str = ""
    payment_requests: list = field(default_factory=list)
    total_amount_cents: int = 0
    created_at: str = ""
    status: str = "pending"  # pending | submitting | complete | failed

    def add_request(self, req: dict):
        self.payment_requests.append(req)
        self.total_amount_cents += int(req.get("amount_cents", 0))


class PayoutBatchStore:
    """Persists payout batches to disk so they survive hub restarts."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path("/root/.empire/payout_batches.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.batches: list = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.batches = json.loads(self.path.read_text())
            except Exception:
                self.batches = []
        else:
            self.batches = []

    def _save(self):
        self.path.write_text(json.dumps(self.batches, indent=2, default=str))

    def add(self, batch: PayoutBatch):
        self.batches.append(asdict(batch))
        self._save()

    def get(self, batch_id: str) -> Optional[dict]:
        for b in self.batches:
            if b["batch_id"] == batch_id:
                return b
        return None

    def update(self, batch_id: str, **fields):
        for b in self.batches:
            if b["batch_id"] == batch_id:
                b.update(fields)
                self._save()
                return b
        return None


def build_payout_batch(
    payouts: list,              # list of PayoutRecord dicts
    crypto_cfg,                 # CryptoConfig
    batch_store: PayoutBatchStore,
) -> PayoutBatch:
    """Build a payout batch with one payment request per pending payout.

    Returns a PayoutBatch with deeplinks ready to open in TokenPocket.
    """
    batch = PayoutBatch(
        batch_id=str(uuid.uuid4())[:12],
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    for p in payouts:
        if p.get("status") != "pending":
            continue
        amount_cents = p.get("amount_cents", 0)
        if amount_cents <= 0:
            continue
        amount_usdc = amount_cents / 100

        # Build a deeplink the operator can click
        # TokenPocket uses solana:<addr>?amount=X&spl-token=Y&memo=Z format
        memo = f"empire-payout:{p['payout_id']}"
        deeplink = (
            f"https://app.tokenpocket.io/solana/{crypto_cfg.vault_wallet}"
            f"?amount={amount_usdc:.6f}"
            f"&spl-token={crypto_cfg.usdc_mint}"
            f"&memo={memo}"
        )
        req = {
            "payout_id": p["payout_id"],
            "amount_cents": amount_cents,
            "amount_usdc": amount_usdc,
            "vault_wallet": crypto_cfg.vault_wallet,
            "usdc_mint": crypto_cfg.usdc_mint,
            "memo": memo,
            "deeplink": deeplink,
            "qr_data": deeplink,  # same data, two formats
            "status": "pending",
        }
        batch.add_request(req)

    batch_store.add(batch)
    logger.info("payout batch %s: %d requests, $%.2f total",
                batch.batch_id, len(batch.payment_requests),
                batch.total_amount_cents / 100)
    return batch