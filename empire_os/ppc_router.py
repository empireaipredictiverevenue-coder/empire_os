"""
Empire OS — PPC router (the "billing brain")
=============================================

The 5 monetization heads:
  1. 90-second PPC (instant bill at 90s)
  2. Settlement (hybrid whale) - $150-$250 upfront + 5-10% backend
  3. PPL (data play) - form fill -> 1..3 local buyers
  4. PPS (calendar lock) - voice qualifies + books -> $150
  5. PPC native arbitrage - cheap clicks into the pipeline above

This module is the BILLING layer, not the call router. The call
router lives in switchboard.py. This sits behind it and decides:
  - which head to bill under
  - how much
  - which invoice line gets a charge_id
  - when to settle on Solana

Routes:
  POST /v1/ppc/lead-intake    {lead_id, source}        -> head chosen, invoiced
  POST /v1/ppc/call-tick      {call_id, duration_s}    -> bill 90s if reached
  POST /v1/ppc/appointment    {lead_id, time}          -> PPS $150
  POST /v1/ppc/close-deal     {call_id, contract_value} -> 5-10% backend
  GET  /v1/ppc/pending        what is mid-flight
  POST /v1/ppc/settle         {invoice_id, source}     -> mark paid (USDC)
"""
from __future__ import annotations
import json, os, secrets, sqlite3, sys, time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.charge import charge as _do_charge

# Ontology bridge: lead-source niches -> seated lane prefixes that ACTUALLY
# exist in the lanes table. We only remap where the raw lead niche has no
# matching lane; where a lane exists (hvac, plumbing, weight_loss, ...) we
# pass it through so the matcher's prefix logic finds the seated buyer.
NICHE_MAP = {
    "roofing": "roof_repair", "roof": "roof_repair",
    "window": "residential_roofing", "solar": "residential_roofing",
    "legal": "legal_services", "lawyer": "legal_services",
    "weight_loss": "weight_loss", "weightloss": "weight_loss",
    "fitness": "weight_loss", "wellness": "weight_loss",
    "ozempic": "weight_loss",
    # hvac, plumbing, electrical, etc. keep their own lane prefix (exists)
}


def normalize_niche(niche: str) -> str:
    n = (niche or "").lower().strip().replace(" ", "_").replace("-", "_")
    return NICHE_MAP.get(n, n)


PORT    = int(os.environ.get("PPC_PORT", "9200"))
FB      = Path("/root/feedback")
LOG     = FB / "ppc_events.jsonl"
HIST    = deque(maxlen=400)
DB      = "/root/empire_os/empire_os.db"
HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8081")


def _post_to_hub(path: str, body: dict) -> dict:
    """Best-effort POST to hub. Returns a dict {ok, status, body, charge_id, ...}
    — never a bare bool. Callers can do `if hub_res.get("ok"): ...`.
    On network/HTTP failure, returns {"ok": False, "error": "..."}."""
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{HUB_URL}{path}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=4) as resp:
            raw = resp.read().decode(errors="replace")
            try:
                parsed = json.loads(raw) if raw else {}
            except Exception:
                parsed = {"raw": raw[:200]}
            if not isinstance(parsed, dict):
                parsed = {"raw": str(parsed)[:200]}
            parsed.setdefault("ok", True)
            parsed["status"] = resp.status
            return parsed
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code,
                "error": "http_error",
                "body": e.read().decode(errors="replace")[:200]}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:200]}

# pricing rules — straight from Empire's 5-headed monetization engine
PRICING = {
    "90s_sprint":      {"flat_cents": 1500, "trigger": "duration_s>=90", "head": 1},
    "hybrid_upfront":  {"flat_cents": 20000, "trigger": "call_connected", "head": 2},
    "hybrid_backend":  {"pct": 0.07,         "trigger": "deal_closed",     "head": 2},
    "ppl_per_buyer":   {"flat_cents": 4500, "cap_buyers": 3,             "head": 3},
    "appointment_pps": {"flat_cents": 15000,                             "head": 4},
    "native_ppc_cpc":  {"flat_cents": 800, "trigger": "click_posted",     "head": 5},
}


def now_iso(): return datetime.now(timezone.utc).isoformat()


def log(level, msg, **fields):
    e = {"ts": now_iso(), "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)


def _deliver_pay_link(buyer_id: str, pay_url: str, memo: str,
                      amount_cents: int) -> None:
    """Email the Solana Pay link to the buyer's inbox.

    The charge generates pay_url + memo but nothing forwarded it before,
    so buyers never received the link and never paid. We look up the buyer's
    email in si_tenant and send via mail_sender (Brevo). Falls back to a
    Telegram operator alert only if no email is on file. Best-effort: a send
    failure must not break the charge.
    """
    if not pay_url:
        return
    usd = f"${amount_cents/100:.2f}"
    # Resolve buyer email from si_tenant
    email = ""
    try:
        import sqlite3
        c = sqlite3.connect("/root/empire_os/empire_os.db")
        row = c.execute("SELECT email FROM si_tenant WHERE tenant_id=?",
                        (buyer_id,)).fetchone()
        c.close()
        email = (row[0] if row else "") or ""
    except Exception:
        pass
    subject = f"Empire OS — your payment link ({usd})"
    body = (
        f"Your Empire OS seat is ready.<br><br>"
        f"Amount due: <b>{usd}</b><br>"
        f'<a href="{pay_url}">Pay now (USDC on Solana)</a><br><br>'
        f"<small>Memo: {memo} — include it so we can activate your seat automatically.</small>"
    )
    if email and "@" in email and "example" not in email:
        try:
            from empire_os import mail_sender as ms
            r = ms._send(email, subject, body)
            log("PAYLINK", "emailed" if r.get("ok") else "email_failed",
                buyer_id=buyer_id, to=email, memo=memo, err=r.get("error", ""))
            if r.get("ok"):
                return
        except Exception as e:
            log("PAYLINK", "email_exc", buyer_id=buyer_id, err=str(e)[:150])
    # Fallback: operator Telegram alert (no email on file / send failed)
    try:
        _post_to_hub("/v1/telegram/alert", {
            "message": (f"\U0001F4B0 Pay link (no buyer email)\nBuyer: {buyer_id}\n"
                        f"Amount: {usd}\nMemo: {memo}\nPay: {pay_url}"),
            "tag": "payment_request"})
        log("PAYLINK", "telegram_fallback", buyer_id=buyer_id, memo=memo)
    except Exception as e:
        log("PAYLINK", "deliver_failed", buyer_id=buyer_id, err=str(e)[:200])


def _invoiced(invoice_id: str, amount_cents: int, head: int,
              reason: str, lead_id: str = "", call_id: str = "",
              buyer_id: str = "") -> dict:
    """Persist a billing event + delegate to hub for canonical charge.

    Two paths:
      1) Always POST to hub /v1/ppc/charge (canonical - hub has the
         buyer wallet DB). If hub reachable, this is the source of
         truth and returns the actual ChargeResult.
      2) ALSO persist locally + legacy log for audit.

    The buyer_id is derived from lead/call ids. Future: switchboard
    should pass explicit buyer attribution instead.
    """
    buyer_id = buyer_id or lead_id or call_id or "unattributed"
    charge_id = "chg_" + secrets.token_hex(6)
    # 1) Delegate to hub - it knows the wallet
    hub_res = _post_to_hub("/v1/ppc/charge", {
        "buyer_id": buyer_id, "head": head, "reason": reason[:200],
        "amount_cents": amount_cents, "currency": "USD",
        "call_id": call_id, "lead_id": lead_id,
    })
    if hub_res.get("ok"):
        charge_id = hub_res.get("charge_id", charge_id)
        status = hub_res.get("status", "failed")
        processor = hub_res.get("processor", "")
        # DELIVER the payment link to the buyer — previously missing,
        # so buyers never received the Solana Pay URL and never paid.
        raw = hub_res.get("raw", {}) or {}
        pay_url = raw.get("pay_url") or hub_res.get("pay_url")
        memo = raw.get("memo") or hub_res.get("memo")
        if pay_url:
            _deliver_pay_link(buyer_id, pay_url, memo or "", amount_cents)
    else:
        status = "failed"
        processor = ""
    # 2) Local persist (mirror) for ppc-router's audit trail
    rec = {
        "charge_id": charge_id,
        "invoice_id": invoice_id,
        "amount_cents": amount_cents,
        "head": head,
        "reason": reason,
        "lead_id": lead_id,
        "call_id": call_id,
        "buyer_id": buyer_id,
        "charge_status": status,
        "charge_processor": processor,
        "hub_res": hub_res,
        "ts": now_iso(),
    }
    log("CHARGE", "billed", **rec)
    # Persist locally too (legacy path - so local DB shows activity)
    try:
        con = sqlite3.connect(DB)
        con.execute(
            "INSERT OR IGNORE INTO si_ppc_invoices "
            "(invoice_id, charge_id, buyer_id, head, lead_id, call_id, "
            " amount_cents, amount_usdc, status, metadata, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (invoice_id, charge_id, buyer_id, head, lead_id, call_id,
             amount_cents, amount_cents/100,
             "paid" if status == "succeeded" else "void",
             json.dumps({"hub_res": hub_res,
                         "buyer_id": buyer_id,
                         "head": head})[:500],
             now_iso()))
        con.commit()
        con.close()
    except Exception as e:
        log("ERROR", "invoice_persist_failed", err=str(e)[:200])
    return rec


def pick_head(lead: dict) -> int:
    """Choose which monetization head applies to a given lead.

    Heuristic:
      - if has phone + form-fill recent -> head 3 (PPL)
      - if has phone + niche=commercial   -> head 2 (hybrid)
      - else                               -> head 5 (native click)
    Real call-time promotions inside switchboard select head 1, 4.
    """
    if lead.get("niche") == "commercial":
        return 2
    if lead.get("source") == "native_ads":
        return 5
    if lead.get("phone"):
        return 3
    return 5


def resolve_buyer_per_lead(niche: str, metro: str = "") -> dict:
    """Map a delivered lead to its seated buyer + that buyer's per-lead rate.

    lane id is 'sub_niche:metro' in the lanes table; occupied_by holds the
    real tenant_id. We read per_lead_cents from that tenant's subscription
    (set at onboard). Returns {tenant_id, per_lead_cents} or {} if none.
    """
    n = normalize_niche(niche)
    try:
        con = sqlite3.connect(DB)
        con.row_factory = sqlite3.Row
        # Pass 1: build candidate lane ids (no close inside this loop)
        cand = []
        if metro:
            cand.append(f"{n}:{metro.upper()}")
        prefixes = [r["pre"] for r in con.execute(
            "SELECT DISTINCT substr(id,1,instr(id,':')-1) AS pre FROM lanes")]
        for pre in prefixes:
            if pre and (pre == n or n in pre or pre in n):
                if metro:
                    cand.append(f"{pre}:{metro.upper()}")
                else:
                    for m in con.execute(
                            "SELECT DISTINCT substr(id,instr(id,':')+1) AS m FROM lanes WHERE id LIKE ?",
                            (f"{pre}:%",)):
                        cand.append(f"{pre}:{m['m']}")
        # Pass 2: resolve buyer (separate loop, safe to close after)
        for lid in cand:
            row = con.execute("SELECT occupied_by FROM lanes WHERE id=?", (lid,)).fetchone()
            tid = (row["occupied_by"] if row else None) or ""
            if not tid or tid == "unattributed":
                continue
            sub = con.execute(
                "SELECT per_lead_cents, status FROM si_subscription WHERE tenant_id=? ORDER BY created_at DESC LIMIT 1",
                (tid,)).fetchone()
            if sub and sub["per_lead_cents"]:
                con.close()
                return {"tenant_id": tid, "per_lead_cents": int(sub["per_lead_cents"])}
        con.close()
    except Exception as e:
        log("RESOLVE", "buyer_lookup_failed", err=str(e)[:200])
    return {}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n) or b"{}")
        r = self.path.split("?")[0]
        if r == "/v1/ppc/lead-intake":   return self.intake(body)
        if r == "/v1/ppc/call-tick":     return self.call_tick(body)
        if r == "/v1/ppc/appointment":   return self.appt(body)
        if r == "/v1/ppc/close-deal":    return self.close(body)
        if r == "/v1/ppc/settle":        return self.settle(body)
        return self.send_json({"error": "not found"}, 404)

    def do_GET(self):
        if self.path.startswith("/v1/ppc/pending"):
            return self.send_json({"events": list(HIST)}, 200)
        if self.path.startswith("/v1/health"):
            return self.send_json({"ok": True,
                                   "heads": len(PRICING),
                                   "pending": len(HIST)}, 200)
        return self.send_json({"error": "not found"}, 404)

    def log_message(self, *a, **k): pass

    # routes
    def intake(self, body):
        lead_id = body.get("lead_id", "")
        src     = body.get("source", "")
        phone   = body.get("phone", "")
        niche   = body.get("niche", "")
        head    = pick_head(body)
        # HYBRID PER-LEAD: if a buyer is seated in this lead's lane, bill THAT
        # buyer their actual per_lead_cents (set at onboard) for the delivery.
        # Fires for any delivered lead to a seated buyer, head-agnostic.
        buyer = resolve_buyer_per_lead(niche, body.get("metro", ""))
        if buyer:
            amt = buyer["per_lead_cents"]
            buyer_id = buyer["tenant_id"]
            inv = "inv_" + secrets.token_hex(6)
            rec = _invoiced(inv, amt, 3,
                            f"PPL: lead delivered to seated buyer {buyer_id}",
                            lead_id=lead_id, buyer_id=buyer_id)
            out = {"lead_id": lead_id, "head": 3, "buyer_id": buyer_id,
                   "amount_usdc": amt/100, "invoice_id": inv,
                   "charge_id": rec["charge_id"]}
            HIST.appendleft(out)
            return self.send_json(out, 200)
        # No seated buyer -> legacy head-based flat billing (fallback)
        if head == 3:
            rules = PRICING["ppl_per_buyer"]
            amt = rules["flat_cents"] * min(3, body.get("buyer_count", 1))
            inv = "inv_" + secrets.token_hex(6)
            rec = _invoiced(inv, amt, head,
                            "PPL: form-fill sold to N local buyers",
                            lead_id=lead_id)
        elif head == 5:
            amt = PRICING["native_ppc_cpc"]["flat_cents"]
            inv = "inv_" + secrets.token_hex(6)
            rec = _invoiced(inv, amt, head,
                            "native ad click-through",
                            lead_id=lead_id)
        else:
            amt = PRICING["hybrid_upfront"]["flat_cents"]
            inv = "inv_" + secrets.token_hex(6)
            rec = _invoiced(inv, amt, head,
                            "hybrid whale up-front CPA",
                            lead_id=lead_id)
        out = {"lead_id": lead_id, "head": head, "amount_usdc": amt/100,
               "invoice_id": inv, "charge_id": rec["charge_id"]}
        HIST.appendleft(out)
        return self.send_json(out, 200)

    def call_tick(self, body):
        cid = body.get("call_id", "")
        dur = int(body.get("duration_s", 0))
        out = {"call_id": cid, "duration_s": dur, "billed": []}
        # head 1 - 90s sprint
        if dur >= 90:
            rules = PRICING["90s_sprint"]
            inv = "inv_" + secrets.token_hex(6)
            rec = _invoiced(inv, rules["flat_cents"], 1,
                            "90s sprint reached", call_id=cid)
            out["billed"].append({**rec, "head": 1,
                                  "amount_usdc": rules["flat_cents"]/100})
        # head 2 - hybrid connected (any duration > 30s with national buyer)
        if dur >= 30 and body.get("buyer_kind") == "national":
            rules = PRICING["hybrid_upfront"]
            inv = "inv_" + secrets.token_hex(6)
            rec = _invoiced(inv, rules["flat_cents"], 2,
                            "hybrid whale up-front (connected)",
                            call_id=cid)
            out["billed"].append({**rec, "head": 2,
                                  "amount_usdc": rules["flat_cents"]/100})
        HIST.appendleft(out)
        return self.send_json(out, 200)

    def appt(self, body):
        lead_id = body.get("lead_id", "")
        time_   = body.get("time", "")
        rules   = PRICING["appointment_pps"]
        inv = "inv_" + secrets.token_hex(6)
        rec = _invoiced(inv, rules["flat_cents"], 4,
                        "PPS: AI booked appointment", lead_id=lead_id)
        out = {"head": 4, "amount_usdc": rules["flat_cents"]/100,
               "invoice_id": inv, "charge_id": rec["charge_id"],
               "scheduled_time": time_}
        HIST.appendleft(out)
        return self.send_json(out, 200)

    def close(self, body):
        cid = body.get("call_id", "")
        cv  = int(body.get("contract_value_cents", 0))
        rules = PRICING["hybrid_backend"]
        amt   = int(cv * rules["pct"])
        inv = "inv_" + secrets.token_hex(6)
        rec = _invoiced(inv, amt, 2,
                        f"backend {int(rules['pct']*100)}% (close)", call_id=cid)
        out = {"head": 2, "amount_usdc": amt/100,
               "contract_value_usdc": cv/100,
               "backend_pct": rules["pct"],
               "invoice_id": inv, "charge_id": rec["charge_id"]}
        HIST.appendleft(out)
        return self.send_json(out, 200)

    def settle(self, body):
        inv = body.get("invoice_id", "")
        # real settlement goes to hub / si_ppc_invoice. Here we just
        # log and return a settlement rec.
        sr = {"settlement_id": "set_" + secrets.token_hex(6),
              "invoice_id": inv,
              "settled_usdc": body.get("amount_usdc", 0),
              "source": body.get("source", "usdc_self"),
              "ts": now_iso()}
        HIST.appendleft(sr)
        return self.send_json(sr, 200)

    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    FB.mkdir(parents=True, exist_ok=True)
    print(f"[{now_iso()}] ppc_router online :{PORT} heads={list(PRICING)}",
          flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
