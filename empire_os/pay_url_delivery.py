"""W2 pay_url auto-delivery.

The hub's POST /v1/ppc/charge mints a real Solana Pay URL and writes
si_charges + si_ppc_invoices, but historically the URL never reached the
buyer. This module closes that loop: after a successful crypto charge
(status='open' or 'succeeded' with a non-empty pay_url), resolve a buyer
email, queue an si_outbox row, and let mail_sender dispatch it.

Design notes
------------
- *Single responsibility.* This file knows about si_outbox, buyer-email
  resolution, and email-render — nothing else. The hub route stays thin.
- *Idempotent.* meta_json carries the source charge_id; the second
  insert for the same charge_id is a no-op (logged + skipped), so
  retries are safe.
- *No simulate.* We never fabricate recipients or URLs. If we can't
  find an email for the buyer we log it loudly and return False — the
  caller still gets the pay_url back in the response.
- *Architecture.* resolve_buyer_email is separate so the resolution
  chain (payment_methods -> tenant -> outreach.prospect_id) is testable
  on its own.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DB = os.environ.get(
    "EMPIRE_DB", "/root/empire_os/empire_os.db"
)


# ── email resolution ─────────────────────────────────────────────────


def resolve_buyer_email(buyer_id: str) -> tuple[str | None, str]:
    """Return (email, source_label) for a buyer.

    Sources checked, in priority order:
      1. si_tenant.delivery_email   (preferred — verified deliverable)
      2. si_tenant.email            (sign-up contact)
      3. si_buyer_payment_methods   — schema has no email col, skip
      4. si_buyer_outreach.email    where prospect_id == buyer_id

    Returns (None, reason) when no source matches.
    """
    if not buyer_id:
        return None, "empty_buyer_id"

    con = sqlite3.connect(DB)
    try:
        # 1+2: tenant
        row = con.execute(
            "SELECT email, delivery_email FROM si_tenant "
            "WHERE tenant_id = ? OR email = ? LIMIT 1",
            (buyer_id, buyer_id),
        ).fetchone()
        if row:
            for col, label in (("delivery_email", "tenant.delivery_email"),
                               ("email", "tenant.email")):
                if row[0 if col == "delivery_email" else 1]:
                    val = (row[0] if col == "delivery_email" else row[1]) or ""
                    if val.strip():
                        return val.strip(), col

        # 3: payment_methods has no email — skip.

        # 4: outreach prospect_id == buyer_id
        row = con.execute(
            "SELECT email FROM si_buyer_outreach "
            "WHERE prospect_id = ? AND email IS NOT NULL "
            "AND TRIM(email) != '' LIMIT 1",
            (buyer_id,),
        ).fetchone()
        if row and row[0]:
            return row[0].strip(), "outreach.prospect_id"

        return None, "no_email_in_any_source"
    finally:
        con.close()


# ── email render ─────────────────────────────────────────────────────


_PAY_URL_TEMPLATE = """\
Pay {dollars:.2f} USDC to activate your head {head} lead delivery.

Buyer: {buyer_id}
Reason: {reason}
Charge: {charge_id}

Click the link below (or copy into any Solana wallet) to pay:
{pay_url}

Memo: {memo}

Once on-chain USDC is detected by solana_listener, your charge will be
marked paid and lead delivery starts within minutes.

— Empire AI
"""


def _render_pay_url_email(pay_url: str, memo: str,
                          amount_cents: int, head: int,
                          buyer_id: str, reason: str,
                          charge_id: str) -> tuple[str, str]:
    dollars = max(0.01, amount_cents / 100)
    subject = f"Empire AI — pay ${dollars:.2f} USDC (head {head})"
    body = _PAY_URL_TEMPLATE.format(
        pay_url=pay_url, memo=memo, head=head, buyer_id=buyer_id,
        reason=reason, charge_id=charge_id, dollars=dollars)
    return subject, body


# ── public entry point ───────────────────────────────────────────────


def deliver_pay_url(res: dict) -> dict:
    """Queue an si_outbox row for a successful pay_url-bearing charge.

    Parameters
    ----------
    res : ChargeResult dict (from /v1/ppc/charge response).
          May also carry an optional ``tag`` string used as a probe
          traceability key (arbitrary caller-supplied label).

    Returns
    -------
    dict with keys: queued (bool), email (str|None), source (str),
                    charge_id (str), outbox_id (int|None),
                    reason (str — failure reason if queued=False)
    """
    out = {"queued": False,
           "email": None, "source": "",
           "charge_id": res.get("charge_id", ""),
           "outbox_id": None, "reason": ""}

    status = (res.get("status") or "").lower()
    pay_url = res.get("pay_url") or ""
    if not pay_url:
        out["reason"] = "no_pay_url"
        return out
    if status not in ("open", "succeeded"):
        out["reason"] = f"non_payable_status={status}"
        return out

    buyer_id = res.get("buyer_id") or ""
    email, source = resolve_buyer_email(buyer_id)
    out["email"] = email
    out["source"] = source
    if not email:
        out["reason"] = "no_email_resolved"
        logger.warning("W2: no email for buyer_id=%s charge_id=%s — "
                       "skipping pay_url delivery", buyer_id,
                       out["charge_id"])
        return out

    subject, body = _render_pay_url_email(
        pay_url=pay_url,
        memo=res.get("memo", ""),
        amount_cents=res.get("amount_cents", 0),
        head=res.get("head", 0),
        buyer_id=buyer_id,
        reason=res.get("reason") or "",
        charge_id=out["charge_id"],
    )

    meta = json.dumps({
        "charge_id": out["charge_id"],
        "pay_url": pay_url,
        "memo": res.get("memo", ""),
        "source": "auto_pay_url",
        "template": "pay_url",
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        # Optional caller-tag (used as a probe-only correlation key).
        "tag": res.get("tag", ""),
    })

    con = sqlite3.connect(DB)
    try:
        # Idempotency: skip if we already queued for this charge_id.
        existing = con.execute(
            "SELECT id FROM si_outbox "
            "WHERE source='auto_pay_url' "
            "AND meta_json LIKE ? LIMIT 1",
            (f'%{out["charge_id"]}%',),
        ).fetchone()
        if existing:
            out["reason"] = "already_queued"
            out["outbox_id"] = existing[0]
            logger.info("W2: pay_url already queued at outbox id=%s "
                        "for charge_id=%s",
                        existing[0], out["charge_id"])
            return out

        cur = con.execute(
            "INSERT INTO si_outbox "
            "(to_email, subject, body, source, status, "
            "meta_json, created_at, recipient_kind) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?, 'buyer')",
            (email, subject, body, "auto_pay_url", meta,
             datetime.now(timezone.utc).isoformat()),
        )
        con.commit()
        out["queued"] = True
        out["outbox_id"] = cur.lastrowid
        logger.info("W2: queued pay_url email outbox id=%s to %s "
                    "(source=%s, charge_id=%s)",
                    out["outbox_id"], email, source, out["charge_id"])
        return out
    finally:
        con.close()
