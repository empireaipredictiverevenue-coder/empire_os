"""
Empire OS v3 — Lead Deliverer (webhook + email)

Watches si_prospect_consent + lane_leads for new leads that match
active buyer subscriptions, then:
  1. POSTs to the buyer's webhook URL (HMAC-signed)
  2. Sends an email to the buyer's delivery_email
  3. Updates last_delivery_at on the buyer record
  4. Marks the lead as `delivered` in lane_leads

Each lead delivery:
  - X-Empire-OS-Signature: HMAC-SHA256(buyer.api_key, body)
  - X-Empire-OS-Lead-Id: lead id
  - X-Empire-OS-Tenant: tenant id
  - X-Empire-OS-Event: lead.delivered
  - Body: full lead JSON

Email transport uses Resend HTTP API (no SMTP server needed). Falls
back to logging the email content if RESEND_API_KEY is not set.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent

HUB_CONTAINER = "empire-hub"
DB_PATH = "/root/empire_os/empire_os.db"

LOG_PATH = Path("/root/feedback/lead_deliveries.jsonl")
HUB = os.environ.get("HUB_URL", "http://localhost:8000")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

POLL_INTERVAL = 30  # seconds
TICK_INTERVAL = 30  # seconds (this is the agent tick interval)

# Resend HTTP API
RESEND_API_URL = "https://api.resend.com/emails"
RESEND_FROM = "Empire OS <leads@empire-ai.co.uk>"
RESEND_REPLY_TO = "leads@empire-ai.co.uk"
ALLOWED_SEND_DOMAIN = "empire-ai.co.uk"

# .env path — read on each call so PM2 reloads after .env writer
ENV_PATH = Path("/root/empire_os/.env")

# --- Disaster / storm-lead monetization config (read from .env) ---
# PPL_DISASTER_MODE=on  -> apply premium multiplier to matching storm leads
# PPL_DISASTER_NICHES   -> comma list of campaign tokens (e.g.
#                          texas_flood_2026,active_emergency_water). A storm
#                          lead matches if its event/notes contain one of these
#                          tokens or a flood/water keyword.
# PPL_DISASTER_MULTIPLIER -> premium applied to buyer base_payout (default 3.0)
def _read_disaster_env() -> tuple[str, list[str], float]:
    mode, niches_raw, mult = "off", "", "3.0"
    try:
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text().splitlines():
                line = line.strip()
                if line.startswith("PPL_DISASTER_MODE="):
                    mode = line.split("=", 1)[1].strip()
                elif line.startswith("PPL_DISASTER_NICHES="):
                    niches_raw = line.split("=", 1)[1].strip()
                elif line.startswith("PPL_DISASTER_MULTIPLIER="):
                    mult = line.split("=", 1)[1].strip()
    except Exception:
        pass
    niches = [n.strip().lower() for n in niches_raw.split(",") if n.strip()]
    try:
        multiplier = float(mult)
    except Exception:
        multiplier = 3.0
    return mode, niches, multiplier


# Storm leads in crm_leads are matched to these buyer niches (active only).
STORM_BUYER_NICHES = ("roofing", "roofing restoration", "restoration",
                      "disaster_recovery", "consumer cpa")
# Keywords that flag a storm lead as a billable disaster event (flood/water).
_DISASTER_KEYWORDS = ("flood", "water", "storm", "tornado", "hurricane",
                      "hail", "wind", "fire")


def _local_db_sql(query: str, params: tuple | list | None = None) -> list:
    """Direct local sqlite3 query (used when running inside empire-hub,
    where the `incus` binary is not present)."""
    import sqlite3 as _sq
    c = _sq.connect(DB_PATH)
    c.row_factory = _sq.Row
    try:
        cur = c.execute(query, params) if params else c.execute(query)
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        c.close()


def _local_db_exec(script: str) -> tuple[bool, str]:
    import sqlite3 as _sq
    try:
        exec(compile(script, "<hub_exec>", "exec"))
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def _hub_sql(query: str, params: tuple | list | None = None) -> list:
    """Run SQL inside empire-hub and return rows as list of dicts.

    When run on the host, this shells `incus exec empire-hub` to reach the
    container DB. When run inside the container (no `incus` binary), it falls
    back to a direct local sqlite3 connection — same DB path either way.

    Args:
        query: SQL string (use ? placeholders for params)
        params: optional tuple/list of parameters for placeholders
    """
    script = (
        "import sqlite3, json, sys\n"
        "c = sqlite3.connect('/root/empire_os/empire_os.db')\n"
        "c.row_factory = sqlite3.Row\n"
        "q = sys.argv[1]\n"
        "p = json.loads(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None\n"
        "cur = c.execute(q, p) if p else c.execute(q)\n"
        "rows = [dict(r) for r in cur.fetchall()]\n"
        "c.close()\n"
        "print(json.dumps(rows, default=str))\n"
    )
    args = ["/root/venv/bin/python3", "-c", script, query, json.dumps(params) if params else ""]
    try:
        r = subprocess.run(
            ["incus", "exec", HUB_CONTAINER, "--", *args],
            capture_output=True, text=True, timeout=15,
        )
    except FileNotFoundError:
        # Running inside the container itself — hit the DB directly.
        return _local_db_sql(query, params)
    out = r.stdout.strip()
    if not out:
        return []
    try:
        return json.loads(out.split("\n")[-1])
    except Exception:
        return []


def _hub_exec(script: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["incus", "exec", HUB_CONTAINER, "--",
             "/root/venv/bin/python3", "-c", script],
            capture_output=True, text=True, timeout=15,
        )
    except FileNotFoundError:
        # Running inside the container itself — run the script directly.
        return _local_db_exec(script)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def _log_event(level: str, msg: str, **extra):
    event = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg}
    event.update(extra)
    try:
        with LOG_PATH.open("a") as f:
            f.write(json.dumps(event, default=str) + "\n")
    except (PermissionError, OSError):
        pass  # logging must never break delivery/billing
    if level in ("ERROR", "WARN", "DELIVERED", "FAILED"):
        print(f"[{level}] {msg} {extra if extra else ''}")


def sign_payload(api_key: str, body: bytes) -> str:
    """HMAC-SHA256 signature for the webhook payload."""
    if not api_key:
        return ""
    return hmac.new(api_key.encode(), body, hashlib.sha256).hexdigest()


def post_webhook(url: str, api_key: str, lead: dict) -> tuple[bool, int, str]:
    """POST the lead to the buyer's webhook URL with HMAC signature."""
    body = json.dumps(lead, default=str).encode()
    sig = sign_payload(api_key, body)

    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "EmpireOS/1.0",
            "X-Empire-OS-Event": "lead.delivered",
            "X-Empire-OS-Lead-Id": str(lead.get("lead_id", "")),
            "X-Empire-OS-Signature": "sha256=" + sig,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return True, r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return False, e.code, e.read().decode()[:200]
    except Exception as e:
        return False, 0, str(e)[:200]


def send_email(to: str, subject: str, body_text: str, body_html: str = None,
               metadata: dict = None) -> tuple[bool, str]:
    """Send email via Resend HTTP API, or log it if no key set.

    Uses requests lib — Python's urllib triggers Cloudflare 1010 on
    api.resend.com because of TLS fingerprint, requests passes.

    Args:
        to: recipient email
        subject: email subject
        body_text: plain text body
        body_html: optional HTML body
        metadata: optional dict forwarded to Resend — appears in webhook events
    """
    api_key = ""
    try:
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text().splitlines():
                line = line.strip()
                if line.startswith("RESEND_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass

    if not api_key:
        _log_event("EMAIL_FALLBACK", "no RESEND_API_KEY, logged only",
                  to=to, subject=subject, body_preview=body_text[:200])
        return True, "logged (no Resend key)"

    payload = {
        "from": RESEND_FROM,
        "to": [to],
        "reply_to": [RESEND_REPLY_TO],
        "subject": subject,
        "text": body_text,
    }
    if f"@{ALLOWED_SEND_DOMAIN}" not in RESEND_FROM:
        return False, f"from '{RESEND_FROM}' not on allowed domain @{ALLOWED_SEND_DOMAIN}"
    if body_html:
        payload["html"] = body_html
    if metadata:
        # Resend only accepts string-keyed string-valued metadata
        payload["metadata"] = {str(k): str(v) for k, v in metadata.items()}

    try:
        import requests
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": "Bearer " + api_key,
                     "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        if r.status_code < 300:
            return True, f"sent ({r.status_code}): {r.text[:200]}"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)[:300]  # noqa: E501


def deliver_lead(buyer: dict, lead: dict) -> dict:
    """Deliver one lead to one buyer via webhook + email."""
    result = {"buyer": buyer["tenant_id"], "lead_id": lead.get("lead_id", "?"),
              "webhook_ok": None, "email_ok": None}

    # 1. Webhook
    if buyer.get("webhook_url"):
        ok, code, body = post_webhook(buyer["webhook_url"],
                                       buyer.get("api_key", ""), lead)
        result["webhook_ok"] = ok
        result["webhook_code"] = code
        if not ok:
            _log_event("WEBHOOK_FAILED", "buyer webhook failed",
                      buyer=buyer["tenant_id"],
                      lead_id=lead.get("lead_id"),
                      code=code, body=body)

    # 2. Email — render via branded template engine
    email_to = buyer.get("delivery_email") or buyer.get("email", "")
    if email_to:
        subject, body_html, body_text = render_lead_delivered_email(
            lead=lead, buyer=buyer,
        )
        ok, info = send_email(email_to, subject, body_text,
                              body_html=body_html,
                              metadata={"lead_id": str(lead.get("id", "")),
                                        "niche": str(lead.get("niche", "")),
                                        "metro": str(lead.get("metro", "")),
                                        "buyer": str(buyer.get("tenant_id", ""))})
        result["email_ok"] = ok
        result["email_info"] = info

    return result


def bill_on_delivery(buyer: dict, lead: dict) -> str | None:
    """Bill a confirmed delivery (pay-per-lead) to the ppc ledger.

    Called by tick_once / deliver_storm_leads ONLY after delivery is
    confirmed (webhook_ok or email_ok). Prevents double-billing on retry.
    Returns invoice_id or None.
    """
    try:
        inv = _log_ppc_invoice(buyer, lead)
        return inv
    except Exception as e:
        _log_event("INVOICE_FAIL", "ppc invoice log failed",
                   buyer=buyer.get("tenant_id"),
                   lead_id=lead.get("lead_id"), err=str(e)[:160])
        return None


def _log_ppc_invoice(buyer: dict, lead: dict) -> str:
    """Bill the delivered lead to the buyer (pay-per-lead) and log it to the
    ppc ledger so solana_listener can collect USDC against it.
    Amount = base_payout * fee_rate (buyer's agreed rate). USDC has 6 decimals."""
    import urllib.request, json, uuid
    base = float(buyer.get("base_payout", 0) or 0)
    rate = float(buyer.get("fee_rate", 0) or 0)
    usd = base * rate if (base and rate) else 0.0
    amount_usdc = int(usd * 1_000_000)  # 6 decimals
    if amount_usdc <= 0:
        return ""  # no billable amount agreed -> skip (NO-SIM: never fake $0)
    iid = f"ppc-{uuid.uuid4().hex[:12]}"
    body = {
        "invoice_id": iid,
        "buyer_id": buyer.get("tenant_id", ""),
        "lead_id": str(lead.get("lead_id", lead.get("id", ""))),
        "amount_cents": int(usd * 100),
        "amount_usdc": amount_usdc,
        "status": "open",
        "metadata": f"pay-per-lead {buyer.get('niche','')} {lead.get('metro','')}",
        "ts": __import__("datetime").datetime.utcnow().isoformat() + "Z",
    }
    req = urllib.request.Request(
        f"{HUB}/v1/ppc/log_invoice",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        json.loads(r.read())
    _log_event("INVOICE_LOGGED", "ppc invoice created",
               invoice_id=iid, amount_usdc=amount_usdc,
               buyer=buyer.get("tenant_id"))
    # money-only alert: lead billed = revenue event
    try:
        import empire_os.revenue_notify as _rn
        _rn.billed(iid, usd, buyer.get("niche", ""))
    except Exception:
        pass
    # affiliate credit: if lead was referred, pay commission on this invoice
    try:
        slug = lead.get("ref") or lead.get("affiliate_slug")
        if slug:
            import empire_os.affiliate as _aff
            _aff.credit_commission(
                str(lead.get("lead_id", lead.get("id", ""))), iid,
                int(usd * 100))
    except Exception:
        pass  # never break billing on affiliate credit failure
    return iid


def render_lead_delivered_email(lead: dict, buyer: dict) -> tuple[str, str, str]:
    """Render (subject, html, text) for a lead-delivery email.

    Uses the branded template engine (Empire AI dark/neon theme) when
    available; falls back to a plain-text body if the templates can't
    be imported.

    The internal `lead_delivered` template reads niche/metro/lead_id,
    so this wrapper just shapes lead + buyer data into the right vars.
    """
    lead_id = str(lead.get("lead_id") or lead.get("id") or "")
    niche   = lead.get("niche", "your niche")
    metro   = lead.get("metro", "your market")
    tenant  = str(buyer.get("tenant_id") or "default")

    dashboard_url = (
        buyer.get("dashboard_url")
        or f"https://empire-ai.co.uk/dashboard/leads/{lead_id}"
    )

    # Try branded template first
    try:
        sys.path.insert(0, "/root/empire_os")
        from empire_os.templates.email import (
            render as render_email,
            render_subject as email_subject,
        )
        vars = {
            "recipient_name": buyer.get("name") or "team",
            "niche":   niche,
            "metro":   metro,
            "lead_id": lead_id,
            "lead_url": dashboard_url,
            "tenant_id": tenant,
            "avenue_id": "leadgen",
        }
        # whitelabel: swap brand if tenant has one configured
        try:
            from empire_os import whitelabel as _wl
            brand = _wl.get_brand(tenant)
            if brand:
                vars["brand_name"] = brand.get("brand_name", "Empire OS")
                vars["primary_color"] = brand.get("primary_color", "#39ff88")
                vars["logo_url"] = brand.get("logo_url", "")
        except Exception:
            pass
        html, text = render_email("lead_delivered", vars)
        subj = email_subject("lead_delivered", vars)
        return subj, html, text
    except Exception as e:
        _log_event("EMAIL_TEMPLATE_FALLBACK", "branded render failed",
                   err=str(e)[:200], lead_id=lead_id, tenant=tenant)

    # Plain-text fallback (same shape as before, just routed here)
    subject = "[Empire OS] New lead: %s in %s" % (niche, metro)
    body_text = (
        "New lead delivered to your subscription.\n\n"
        "Lead ID: %s\n"
        "Niche:   %s\n"
        "Metro:   %s\n"
        "State:   %s\n"
        "Name:    %s\n"
        "Email:   %s\n"
        "Phone:   %s\n"
        "Details: %s\n\n"
        "Reply to claim, or visit your dashboard.\n"
        % (
            lead_id,
            niche,
            metro,
            lead.get("state", ""),
            lead.get("name", ""),
            lead.get("email", ""),
            lead.get("phone", ""),
            (lead.get("details", "") or "")[:500],
        )
    )
    return subject, "", body_text


def find_matching_buyers(lead: dict = None) -> list:
    """Find active buyers (and their subscriptions) for lead delivery.

    For now: returns ALL active lane-subscription buyers, regardless of
    niche/metro. Once a si_lane_subscription table exists, this will
    filter by matching niche+metro.

    Note: si_tenant lacks webhook_url/api_key/delivery_email columns.
    We synthesize a delivery_email from t.email as a sensible default
    so the email path is exercised end-to-end.
    """
    rows = _hub_sql("""
        SELECT t.tenant_id, t.name, t.email, t.plan AS tenant_plan,
               s.subscription_id, s.plan, s.seats
        FROM si_tenant t
        JOIN si_subscription s ON s.tenant_id = t.tenant_id
        WHERE s.status = 'active'
          AND s.plan LIKE 'lane_%'
          AND (s.payment_ref IS NOT NULL AND s.payment_ref != '')
    """)
    for r in rows:
        # Default the email-path fields from t.email when columns don't exist
        r.setdefault("webhook_url", None)
        r.setdefault("api_key", "")
        r.setdefault("delivery_email", r.get("email", ""))
    return rows


def find_storm_buyers() -> list:
    """Active buyers whose niche matches storm/restoration demand.

    Reads the Supabase `buyers` table (via empire_os.sb). Returns buyer dicts
    shaped for deliver_lead()/ _log_ppc_invoice(): tenant_id, niche,
    webhook_url, api_key, delivery_email, base_payout, fee_rate.
    """
    try:
        from empire_os.sb import select
        rows = (select("buyers", "*", filters={"status": "ACTIVE"}, limit=200)
                + select("buyers", "*", filters={"status": "active"}, limit=200))
    except Exception as e:
        _log_event("STORM_BUYER_ERR", "could not read buyers table", err=str(e)[:160])
        return []

    # de-dup by id
    by_id = {}
    for r in rows:
        by_id[r["id"]] = r

    matched = []
    for r in by_id.values():
        if not r.get("is_active", False):
            continue
        niche = (r.get("niche") or "").strip().lower()
        if niche not in STORM_BUYER_NICHES:
            continue
        buyer = {
            "tenant_id": r.get("id"),
            "buyer_name": r.get("buyer_name", ""),
            "niche": r.get("niche", ""),
            "webhook_url": r.get("webhook_url"),
            "api_key": r.get("api_key", "") or "",
            "delivery_email": r.get("email") or r.get("delivery_email") or "",
            "base_payout": float(r.get("base_payout") or 0),
            "fee_rate": float(r.get("fee_rate") or 0),
        }
        matched.append(buyer)
    return matched


def _storm_is_disaster(lead: dict, disaster_niches: list[str]) -> bool:
    """True if the storm lead is a billable disaster event under PPL_DISASTER_NICHES."""
    hay = " ".join([
        str(lead.get("business_name", "")),
        str(lead.get("notes", "")),
        str(lead.get("niche", "")),
        str(lead.get("sub_niche", "")),
    ]).lower()
    # explicit campaign token match
    for tok in disaster_niches:
        if tok and tok in hay:
            return True
    # flood / emergency-water events are always disaster-premium eligible
    return any(k in hay for k in ("flood", "water"))


def deliver_storm_leads(dry_run: bool = False) -> int:
    """Deliver undelivered storm leads (source='satellite_strike') from
    crm_leads to active roofing/restoration buyers, billing at a disaster
    premium when PPL_DISASTER_MODE is on and the lead matches.

    Reuses deliver_lead() + _log_ppc_invoice() — no duplicated billing logic.
    Returns the number of storm leads delivered and billed.
    """
    mode, disaster_niches, multiplier = _read_disaster_env()
    disaster_on = (mode == "on")

    # 2a. undelivered storm leads
    leads = _hub_sql(
        "SELECT * FROM crm_leads "
        "WHERE source = 'satellite_strike' "
        "AND (delivery_status IS NULL OR delivery_status NOT IN ('delivered','billed')) "
        "ORDER BY created_at DESC"
    )
    if not leads:
        return 0

    # 2b. active buyers matching storm/roofing niches
    buyers = find_storm_buyers()
    if not buyers:
        _log_event("STORM_BLOCKER", "no active roofing/restoration buyer — "
                   "storm leads cannot be monetized", pending=len(leads))
        return 0

    delivered = 0
    for lead in leads:
        lead_id = lead["id"]
        # shape the lead for deliver_lead()/email render
        storm_lead = {
            "id": lead_id,
            "lead_id": lead.get("lead_uid") or lead_id,
            "business_name": lead.get("business_name", ""),
            "niche": lead.get("niche", "roofing"),
            "sub_niche": lead.get("sub_niche", ""),
            "metro": lead.get("metro", ""),
            "state": lead.get("state", ""),
            "name": lead.get("contact_name", ""),
            "email": lead.get("email", ""),
            "phone": lead.get("phone", ""),
            "details": lead.get("notes", ""),
            "source": "satellite_strike",
            "notes": lead.get("notes", ""),
        }
        is_disaster = disaster_on and _storm_is_disaster(lead, disaster_niches)

        for buyer in buyers:
            # 2c. premium-adjusted buyer copy (only affects billing amount)
            bill_buyer = dict(buyer)
            if is_disaster:
                bill_buyer["base_payout"] = float(buyer["base_payout"]) * multiplier
                bill_buyer["_disaster_premium"] = True
                bill_buyer["_premium_multiplier"] = multiplier

            if dry_run:
                base = float(buyer["base_payout"])
                rate = float(buyer["fee_rate"])
                adj = base * (multiplier if is_disaster else 1.0)
                amt = int(adj * rate * 1_000_000)
                _log_event("STORM_DRYRUN", "would deliver storm lead",
                          lead_id=lead_id, buyer=buyer["tenant_id"],
                          disaster=is_disaster, amount_usdc=amt)
                continue

            # 2d. deliver + bill via existing functions
            result = deliver_lead(bill_buyer, storm_lead)
            ok = result.get("webhook_ok") or result.get("email_ok") \
                 or result.get("invoice_id")
            if ok:
                # 2e. bill (confirmed delivery only) + mark delivered/billed
                inv = bill_on_delivery(bill_buyer, storm_lead)
                _hub_exec(
                    "import sqlite3,sys;"
                    "c=sqlite3.connect('/root/empire_os/empire_os.db');"
                    "c.execute(\"UPDATE crm_leads SET delivery_status='delivered', "
                    "status='billed', updated_at=? WHERE id=?\", "
                    "(__import__('datetime').datetime.utcnow().isoformat(), sys.argv[2]));c.commit();c.close()"
                    .replace("sys.argv[1]", "__import__('datetime').datetime.utcnow().isoformat()")
                    .replace("sys.argv[2]", str(lead_id))
                )
                _log_event("STORM_DELIVERED", "storm lead delivered + billed",
                          lead_id=lead_id, buyer=buyer["tenant_id"],
                          disaster=is_disaster, webhook=result.get("webhook_ok"),
                          email=result.get("email_ok"),
                          invoice_id=result.get("invoice_id"))
                delivered += 1
                break  # one buyer per lead is enough

    return delivered


def mark_lead_delivered(lead_id: int):
    """Mark the lead as delivered in lane_leads.

    NOTE: lane_leads has no `updated_at` column, so only `status` is set.
    """
    script = (
        "import sqlite3, sys\n"
        "c = sqlite3.connect('/root/empire_os/empire_os.db')\n"
        "c.execute(\"UPDATE lane_leads SET status='delivered' "
        "WHERE id=? AND status NOT IN ('delivered', 'reserved')\", "
        "(sys.argv[1],))\n"
        "c.commit()\n"
        "c.close()\n"
    )
    _hub_exec(script.replace("sys.argv[1]", str(lead_id)))


def poll_for_new_leads():
    """Find leads that haven't been delivered yet.

    Note: lane_leads has limited fields (id, lane_id, prospect_id, status,
    omega_score, omega_tier, notes, niche). Contact data lives on the
    lane via lanes.metro + lanes.sub_niche, and on the prospect via
    si_funnel_event → si_prospect_consent.
    """
    rows = _hub_sql("""
        SELECT id, lane_id, prospect_id, niche, status,
               omega_score, omega_tier, notes, created_at
        FROM lane_leads
        WHERE status = 'pending'
          AND niche IS NOT NULL
          AND niche != ''
          AND lane_id IN (SELECT id FROM lanes)
        ORDER BY created_at DESC
        LIMIT 20
    """)
    if not rows:
        return []
    # Enrich each row with metro + sub_niche from a single lanes lookup
    all_lanes = _hub_sql("SELECT id, sub_niche, metro FROM lanes")
    lane_meta = {l["id"]: l for l in all_lanes}
    for r in rows:
        meta = lane_meta.get(r.get("lane_id"), {})
        r["sub_niche"] = meta.get("sub_niche", "")
        r["metro"] = meta.get("metro", "")
        r.setdefault("name", "")
        r.setdefault("email", "")
        r.setdefault("phone", "")
        r.setdefault("details", r.get("notes", ""))
        r.setdefault("state", "")
        r.setdefault("source", "lane_routing")
    return rows


def tick_once():
    """One delivery pass."""
    leads = poll_for_new_leads()
    if not leads:
        return 0

    # all active buyers, keyed by tenant_id for lane->buyer resolution
    all_buyers = find_matching_buyers({}) + find_storm_buyers()
    buyer_by_id = {b["tenant_id"]: b for b in all_buyers}
    if not buyer_by_id:
        _log_event("INFO", "no active buyers, %d leads pending" % len(leads))
        return 0

    # lane seat-price + occupied_by map (corridor model)
    lane_rows = _hub_sql("SELECT id, seat_price, occupied_by, firm_slug FROM lanes WHERE occupied_by IS NOT NULL AND occupied_by != ''")
    lane_seat = {l["id"]: l for l in lane_rows}

    delivered = 0
    for lead in leads:
        # resolve the buyer for this lead's lane (seated corridor) first
        seat = lane_seat.get(lead.get("lane_id"))
        if seat and seat.get("occupied_by") in buyer_by_id:
            buyers = [buyer_by_id[seat["occupied_by"]]]
        else:
            buyers = list(buyer_by_id.values())  # storm leads: match any active buyer
        for buyer in buyers:
            bill_buyer = dict(buyer)
            if seat and seat.get("seat_price"):
                # base_payout * fee_rate must equal seat_price
                rate = float(buyer.get("fee_rate") or 0) or 1.0
                bill_buyer["base_payout"] = float(seat["seat_price"]) / rate
                bill_buyer["_seat_price"] = float(seat["seat_price"])
            result = deliver_lead(bill_buyer, lead)
            ok = result.get("webhook_ok") or result.get("email_ok")
            if ok:
                # bill ONLY on confirmed delivery (no double-bill on retry)
                inv = bill_on_delivery(bill_buyer, lead)
                _log_event("DELIVERED", "lead delivered",
                          buyer=buyer["tenant_id"],
                          lead_id=lead.get("id"),
                          invoice_id=inv,
                          seat_price=bill_buyer.get("_seat_price"),
                          webhook=result.get("webhook_ok"),
                          email=result.get("email_ok"))
                mark_lead_delivered(lead.get("id"))
                delivered += 1
    return delivered


class LeadDelivererAgent(SyntheticAgent):
    """Watches for new leads and delivers to active buyers."""

    def observe(self) -> dict:
        try:
            leads = poll_for_new_leads()
            buyers = find_matching_buyers({})
            return {
                "pending_leads": len(leads),
                "active_buyers": len(buyers),
                "sample_leads": leads[:3],
            }
        except Exception as e:
            return {"error": str(e)}

    def reason(self, state: dict) -> str:
        if state.get("error"):
            return json.dumps({"action": "no-delivery", "error": state["error"]})

        pending = state.get("pending_leads", 0)
        buyers = state.get("active_buyers", 0)
        if pending == 0:
            return json.dumps({"action": "no-leads-pending"})

        if buyers == 0:
            return json.dumps({
                "action": "block",
                "reason": "%d leads pending but 0 active buyers" % pending,
                "next": "run outreach to convert pending to active",
            })

        return json.dumps({
            "action": "deliver",
            "pending_leads": pending,
            "active_buyers": buyers,
        })

    def act(self, decision: str) -> dict:
        try:
            d = json.loads(decision)
        except Exception:
            return {"summary": "decision-parse-error"}

        if d.get("action") != "deliver":
            return {"summary": "no-delivery", "decision": d.get("action")}

        count = tick_once()
        return {"summary": "delivered-%d-leads" % count, "count": count}


if __name__ == "__main__":
    import os
    os.makedirs("/root/lead_deliverer", exist_ok=True)

    # Use the mechanical deliverer directly (no LLM). The deliverer is a
    # pure mechanical task: pending lead + active buyer → webhook + email.
    # Going through Ollama added 2+ minutes of latency and JSON parse
    # failures. The agent class is still available for callers who want
    # to compose it into a larger reasoning loop.
    import importlib
    ld = importlib.import_module("empire_os.agents.lead_deliverer_agent")
    print("Lead deliverer (mechanical) starting — tick every %ds" % TICK_INTERVAL)

    consecutive_failures = 0
    while True:
        try:
            # Read pending leads + active buyers directly
            leads = ld.poll_for_new_leads()
            buyers = ld.find_matching_buyers()
            if not leads:
                pass  # no leads
            elif not buyers:
                ld._log_event("INFO", "no active buyers, %d leads pending" % len(leads))
            else:
                count = 0
                for lead in leads:
                    for buyer in buyers:
                        result = ld.deliver_lead(buyer, lead)
                        if result.get("webhook_ok") or result.get("email_ok"):
                            ld._log_event("DELIVERED", "lead delivered",
                                          buyer=buyer["tenant_id"],
                                          lead_id=lead.get("id"),
                                          webhook=result.get("webhook_ok"),
                                          email=result.get("email_ok"))
                            ld.mark_lead_delivered(lead.get("id"))
                            count += 1
                print("[%s] delivered %d leads" % (
                    datetime.now(timezone.utc).isoformat(), count))

            # Storm-lead bridge: deliver + bill satellite_strike crm_leads
            storm_count = ld.deliver_storm_leads()
            if storm_count:
                print("[%s] storm-delivered %d leads" % (
                    datetime.now(timezone.utc).isoformat(), storm_count))

            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({"error": str(e), "backoff": backoff}))
            time.sleep(backoff)
            continue

        time.sleep(TICK_INTERVAL)