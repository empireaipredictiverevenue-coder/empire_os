"""
Empire OS — Pay-Per-Lead (PPL) service for Texas flood response.

A standalone FastAPI on PORT (env PPL_PORT, default 9210) that:
  - serves the "ugly landing page" at /v1/ppl/page/<slug>
  - accepts ZIP-code submissions at POST /v1/ppl/intake
  - validates the ZIP against PPL_ALLOWED_ZIPS (comma-separated prefixes)
  - mirrors the lead to hub /v1/leads/intake (best-effort, non-blocking)
  - fires dispatch webhook (PPL_DISPATCH_WEBHOOK_URL); retries on fail
  - supports DISASTER_MODE guard (default off) — refuses active-emergency
    niches until operator flips it on
  - all events land in /root/feedback/ppl_events.jsonl
  - all accepted leads in si_ppl_leads table

This service does NOT depend on hub.py or the synthetic_agents stack.
Hub forward is a thin POST; loss of hub does not block dispatch.

Endpoints:
  GET  /v1/ppl/health             — liveness + dispatch config snapshot
  GET  /v1/ppl/pending            — JSON: undelivered dispatches
  GET  /v1/ppl/leads              — last 50 leads
  GET  /v1/ppl/page/<slug>        — landing page HTML
  GET  /v1/ppl/dashboard          — operator traffic view
  POST /v1/ppl/intake             — main lead intake

Run:
  /root/venv/bin/python3 /root/empire_os/empire_os/ppl_service.py

Cadence:
  - Dispatcher loop runs in a background thread, polls every
    PPL_DISPATCH_INTERVAL_SEC; retries up to PPL_DISPATCH_RETRY_MAX.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# Load /root/empire_os/.env if present (operator-friendly: launching
# the service directly works without `set -a; . .env; set +a`).
_ENV_PATH = Path("/root/empire_os/.env")
if _ENV_PATH.exists():
    try:
        for ln in _ENV_PATH.read_text().splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass

sys.path.insert(0, "/root/empire_os")

PORT = int(os.environ.get("PPL_PORT", "9210"))
HUB = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
DB_PATH = os.environ.get("DB_PATH", "/root/empire_os/empire_os.db")
DISPATCH_URL = os.environ.get("PPL_DISPATCH_WEBHOOK_URL", "").strip()
DISPATCH_TEL = os.environ.get("PPL_DISPATCH_TEL", "").strip()
DISPATCH_NAME = os.environ.get("PPL_DISPATCH_NAME", "Local Dispatch").strip()
DISPATCH_INTERVAL = int(os.environ.get("PPL_DISPATCH_INTERVAL_SEC", "30"))
DISPATCH_RETRY_MAX = int(os.environ.get("PPL_DISPATCH_RETRY_MAX", "3"))
ALLOWED_ZIPS_RAW = os.environ.get("PPL_ALLOWED_ZIPS", "").strip()
MIRROR_TO_HUB = os.environ.get("PPL_MIRROR_TO_HUB", "1") == "1"
DISASTER_MODE = os.environ.get("PPL_DISASTER_MODE", "off").lower() == "on"
DISASTER_NICHES = {
    n.strip().lower()
    for n in os.environ.get("PPL_DISASTER_NICHES",
                            "texas_flood_2026,active_emergency_water").split(",")
    if n.strip()
}

FB = Path("/root/feedback")
FB.mkdir(parents=True, exist_ok=True)
EVENTS_LOG = FB / "ppl_events.jsonl"
LEADS_LOG = FB / "ppl_leads.jsonl"

ZIP_PREFIXES = tuple(p.strip() for p in ALLOWED_ZIPS_RAW.split(",") if p.strip())
ZIP_PATTERN = re.compile(r"^\d{5}$")

# ── DB ──────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS si_ppl_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    zip TEXT NOT NULL,
    name TEXT,
    phone TEXT,
    message TEXT,
    niche TEXT NOT NULL DEFAULT 'texas_flood_2026',
    source TEXT,
    status TEXT NOT NULL DEFAULT 'received',  -- received|dispatched|failed|refused|disaster_blocked
    dispatch_attempts INTEGER NOT NULL DEFAULT 0,
    dispatch_response TEXT,
    dispatch_id TEXT,
    hub_mirror_status TEXT,
    ip TEXT,
    user_agent TEXT
);
CREATE INDEX IF NOT EXISTS si_ppl_leads_status ON si_ppl_leads(status);
CREATE INDEX IF NOT EXISTS si_ppl_leads_zip ON si_ppl_leads(zip);
"""


def db():
    cnx = sqlite3.connect(DB_PATH)
    cnx.row_factory = sqlite3.Row
    return cnx


def init_db():
    cnx = db()
    cnx.executescript(SCHEMA_SQL)
    cnx.commit()
    cnx.close()


# ── Logging ─────────────────────────────────────────────────────────────
def log_event(level: str, msg: str, **kw: Any) -> None:
    e = {
        "ts": now_iso(),
        "level": level,
        "msg": msg,
        **kw,
    }
    with EVENTS_LOG.open("a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "ALERT"):
        print(json.dumps(e), file=sys.stderr, flush=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Validation ──────────────────────────────────────────────────────────
def _validate_zip(zip_value: str) -> tuple[bool, str]:
    if not zip_value or not isinstance(zip_value, str):
        return False, "zip_missing"
    zip_value = zip_value.strip()
    if not ZIP_PATTERN.match(zip_value):
        return False, "zip_format"
    if not ZIP_PREFIXES:
        # no allow-list configured → accept any valid ZIP
        return True, ""
    for prefix in ZIP_PREFIXES:
        if zip_value.startswith(prefix):
            return True, ""
    return False, "zip_not_in_service_area"


# ── Dispatch ────────────────────────────────────────────────────────────
def fire_dispatch(lead_id: int, lead: dict) -> tuple[bool, str]:
    """HTTP POST to PPL_DISPATCH_WEBHOOK_URL. Returns (ok, response_text)."""
    if not DISPATCH_URL:
        return False, "dispatch_webhook_not_configured"
    body = {
        "lead_id": lead_id,
        "event": "ppl.lead.dispatched",
        "ts": now_iso(),
        "zip": lead.get("zip"),
        "niche": lead.get("niche"),
        "name": lead.get("name"),
        "phone": lead.get("phone"),
        "message": lead.get("message"),
        "callback_tel": DISPATCH_TEL or None,
        "callback_name": DISPATCH_NAME or None,
    }
    try:
        req = urllib.request.Request(
            DISPATCH_URL,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "User-Agent": "EmpireOS-PPL/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            text = resp.read().decode(errors="replace")[:500]
            ok = resp.status in (200, 201, 202, 204)
            return ok, f"HTTP {resp.status}: {text}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:200]


def update_dispatch_attempt(lead_id: int, ok: bool, response: str) -> None:
    cnx = db()
    try:
        cnx.execute(
            "UPDATE si_ppl_leads "
            "SET dispatch_attempts = dispatch_attempts + 1, "
            "    dispatch_response = ?, "
            "    status = CASE WHEN ? THEN 'dispatched' "
            "                  ELSE status END "
            "WHERE id = ?",
            (response[:500], int(ok), lead_id))
        cnx.commit()
    finally:
        cnx.close()


# ── Hub mirror (best-effort, non-blocking) ──────────────────────────────
def mirror_to_hub(lead_id: int, lead: dict) -> None:
    if not MIRROR_TO_HUB:
        return
    body = {
        "source": "ppl-9210",
        "niche": lead.get("niche", "texas_flood_2026"),
        "intent": "emergency_water_removal",
        "consent": "explicit_form_submit",
        "lead_id": f"ppl-{lead_id}",
        "email": lead.get("email") or f"ppl+{lead_id}@empire-ai.co.uk",
        "name": lead.get("name") or f"Lead #{lead_id}",
        "phone": lead.get("phone") or "",
        "metro": zip_to_metro(lead.get("zip", "")),
        "metadata": {
            "zip": lead.get("zip"),
            "ppl_lead_id": lead_id,
            "source": "ppl_landing_page",
        },
    }
    try:
        req = urllib.request.Request(
            f"{HUB}/v1/leads/intake",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            hub_status = "ok"
            cnx = db()
            try:
                cnx.execute(
                    "UPDATE si_ppl_leads SET hub_mirror_status = ? WHERE id = ?",
                    (f"ok:{resp.status}", lead_id))
                cnx.commit()
            finally:
                cnx.close()
    except Exception as e:
        cnx = db()
        try:
            cnx.execute(
                "UPDATE si_ppl_leads SET hub_mirror_status = ? WHERE id = ?",
                (f"fail:{type(e).__name__}:{str(e)[:80]}", lead_id))
            cnx.commit()
        finally:
            cnx.close()


def zip_to_metro(z: str) -> str:
    """Trivial mapping; real service would resolve from a zip-to-metro db."""
    if not z:
        return ""
    if z.startswith(("788", "789")):
        return "Uvalde_TX"
    if z.startswith(("78006", "78028", "78029")):
        return "Kerrville_TX"
    if z.startswith("78024"):
        return "Sabinal_TX"
    return f"{z[:3]}xx_TX"


# ── Dispatcher loop (background thread) ─────────────────────────────────
def dispatcher_loop():
    """Re-fire dispatch for received/failed leads up to RETRY_MAX times."""
    log_event("INFO", "dispatcher_started",
              interval_s=DISPATCH_INTERVAL,
              retry_max=DISPATCH_RETRY_MAX,
              webhook_configured=bool(DISPATCH_URL))
    while True:
        time.sleep(DISPATCH_INTERVAL)
        try:
            cnx = db()
            rows = [dict(r) for r in cnx.execute(
                "SELECT id, * FROM si_ppl_leads "
                "WHERE status IN ('received', 'failed') "
                "AND dispatch_attempts < ? "
                "ORDER BY id ASC LIMIT 20",
                (DISPATCH_RETRY_MAX,)).fetchall()]
            cnx.close()
            for lead in rows:
                ok, resp = fire_dispatch(lead["id"], dict(lead))
                update_dispatch_attempt(lead["id"], ok, resp)
                log_event(
                    "EVENT" if ok else "ERROR",
                    "dispatch_attempt",
                    lead_id=lead["id"],
                    ok=ok,
                    response=resp[:120],
                    n_attempts=lead["dispatch_attempts"] + 1,
                )
        except Exception as e:
            log_event("ERROR", "dispatcher_loop", err=str(e)[:200])


# ── HTTP handlers ───────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a, **kw):  # silence default access log
        pass

    def _send(self, code: int, body: bytes,
              content_type: str = "application/json"):
        try:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def _read_body(self) -> tuple[dict | None, str]:
        try:
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n) if n else b""
            data = json.loads(raw.decode() or "{}")
            return data, ""
        except json.JSONDecodeError as e:
            return None, f"json_decode:{e}"
        except Exception as e:
            return None, f"read_error:{type(e).__name__}"

    def _client_ip(self) -> str:
        return self.headers.get("X-Forwarded-For",
                                self.client_address[0] or "")

    # ── routes ────────────────────────────────────────────────────────
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/v1/ppl/health":
            return self._health()
        if path == "/v1/ppl/pending":
            return self._pending()
        if path == "/v1/ppl/leads":
            return self._leads()
        if path == "/v1/ppl/dashboard":
            return self._dashboard()
        if path.startswith("/v1/ppl/page/"):
            slug = path[len("/v1/ppl/page/"):]
            return self._page(slug)
        self._send(404, json.dumps({"error": "not_found",
                                    "path": path}).encode())

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/v1/ppl/intake":
            return self._intake()
        self._send(404, json.dumps({"error": "not_found",
                                    "path": path}).encode())

    # ── handlers ──────────────────────────────────────────────────────
    def _health(self):
        body = {
            "status": "online",
            "ts": now_iso(),
            "service": "ppl-9210",
            "disaster_mode": DISASTER_MODE,
            "disaster_niches": sorted(DISASTER_NICHES),
            "dispatch_webhook_configured": bool(DISPATCH_URL),
            "dispatch_tel_configured": bool(DISPATCH_TEL),
            "allowed_zip_prefixes": list(ZIP_PREFIXES),
            "mirroring_to_hub": MIRROR_TO_HUB,
        }
        self._send(200, json.dumps(body).encode())

    def _pending(self):
        cnx = db()
        rows = [dict(r) for r in cnx.execute(
            "SELECT id, ts, zip, name, phone, niche, status, "
            "       dispatch_attempts, dispatch_response "
            "FROM si_ppl_leads "
            "WHERE status IN ('received','failed') "
            "ORDER BY id DESC LIMIT 50").fetchall()]
        cnx.close()
        self._send(200, json.dumps({"pending": rows,
                                    "count": len(rows)}).encode())

    def _leads(self):
        cnx = db()
        rows = [dict(r) for r in cnx.execute(
            "SELECT id, ts, zip, niche, status, dispatch_attempts, "
            "       hub_mirror_status "
            "FROM si_ppl_leads ORDER BY id DESC LIMIT 50").fetchall()]
        cnx.close()
        self._send(200, json.dumps({"leads": rows,
                                    "count": len(rows)}).encode())

    def _dashboard(self):
        cnx = db()
        totals = {
            k: v for k, v in cnx.execute(
                "SELECT status, COUNT(*) FROM si_ppl_leads GROUP BY status"
            ).fetchall()
        }
        recent = [dict(r) for r in cnx.execute(
            "SELECT id, ts, zip, niche, status "
            "FROM si_ppl_leads ORDER BY id DESC LIMIT 20").fetchall()]
        cnx.close()
        # simple HTML
        rows_html = "\n".join(
            f"<tr><td>{r['id']}</td><td>{r['ts'][:19]}</td>"
            f"<td>{r['zip']}</td><td>{r['niche']}</td>"
            f"<td>{r['status']}</td></tr>"
            for r in recent
        ) or "<tr><td colspan=5>No leads yet</td></tr>"
        body = f"""<!doctype html>
<html><head><title>PPL Dashboard</title>
<style>body{{font-family:system-ui;margin:0;background:#111;color:#eee}}
header{{background:#ffcc00;color:#000;padding:12px 24px}}
main{{padding:24px}}
table{{border-collapse:collapse;width:100%}}
td,th{{padding:6px 10px;border-bottom:1px solid #333;text-align:left}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;margin-right:6px}}
.b-on{{background:#5b1a1a;color:#fff}} .b-off{{background:#1a4a1a;color:#fff}}
.warn{{background:#5b4a1a;padding:12px;border-radius:4px;margin:12px 0}}
</style></head><body>
<header><h1>PPL Operator Dashboard</h1></header>
<main>
<p><span class="badge b-{'on' if DISASTER_MODE else 'off'}">
DISASTER_MODE = {'on' if DISASTER_MODE else 'off'}</span>
<span class="badge b-{'on' if DISPATCH_URL else 'off'}">
Dispatch webhook: {'configured' if DISPATCH_URL else 'NOT SET'}</span>
<span class="badge b-{'on' if DISPATCH_TEL else 'off'}">
Tel: {DISPATCH_TEL or 'NOT SET'}</span></p>
{('<div class="warn">DISASTER_MODE is ON — leads tagged with: '
   + ', '.join(sorted(DISASTER_NICHES))
   + ' will be REFUSED until operator disables.</div>'
   ) if DISASTER_MODE else ''}
<h2>Funnel totals</h2>
<pre>{json.dumps(totals, indent=2)}</pre>
<h2>Recent leads (last 20)</h2>
<table><tr><th>id</th><th>ts</th><th>zip</th><th>niche</th><th>status</th></tr>
{rows_html}</table>
</main></body></html>"""
        self._send(200, body.encode(), "text/html; charset=utf-8")

    def _page(self, slug: str):
        # Only one page exists today. Reject unknown slugs.
        if slug not in ("texas-flood-water-removal",):
            self._send(404, b"<h1>Page not found</h1>", "text/html")
            return
        html = render_landing_page(
            tel=DISPATCH_TEL,
            dispatch_name=DISPATCH_NAME,
            allowed_zip_prefixes=list(ZIP_PREFIXES),
            disaster_mode=DISASTER_MODE,
        )
        self._send(200, html.encode(), "text/html; charset=utf-8")

    def _intake(self):
        data, err = self._read_body()
        if err:
            log_event("WARN", "intake_bad_json", err=err)
            self._send(400, json.dumps({"ok": False, "error": err}).encode())
            return

        zip_value = (data.get("zip") or "").strip()
        name = (data.get("name") or "").strip() or None
        phone = (data.get("phone") or "").strip() or None
        message = (data.get("message") or "").strip() or None
        niche = (data.get("niche") or "texas_flood_2026").strip()
        source = data.get("source") or "landing_page"

        # 1. ZIP validation
        ok, reason = _validate_zip(zip_value)
        if not ok:
            log_event("WARN", "intake_bad_zip", zip=zip_value, reason=reason)
            self._send(400, json.dumps({"ok": False,
                                        "error": reason}).encode())
            return

        # 2. Disaster guard
        if DISASTER_MODE and niche.lower() in DISASTER_NICHES:
            cnx = db()
            cur = cnx.execute(
                "INSERT INTO si_ppl_leads "
                "(ts, zip, name, phone, message, niche, source, "
                " status, ip, user_agent) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'disaster_blocked', ?, ?)",
                (now_iso(), zip_value, name, phone, message, niche, source,
                 self._client_ip(),
                 self.headers.get("User-Agent", "")))
            cnx.commit()
            lead_id = cur.lastrowid
            cnx.close()
            log_event("ALERT", "intake_disaster_blocked",
                      lead_id=lead_id, niche=niche)
            self._send(503, json.dumps({
                "ok": False,
                "error": "disaster_mode_active",
                "lead_id": lead_id,
                "msg": "This service is paused for active-emergency leads. "
                       "Please call your county emergency management line.",
            }).encode())
            return

        # 3. Persist
        cnx = db()
        cur = cnx.execute(
            "INSERT INTO si_ppl_leads "
            "(ts, zip, name, phone, message, niche, source, status, "
            " ip, user_agent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'received', ?, ?)",
            (now_iso(), zip_value, name, phone, message, niche, source,
             self._client_ip(),
             self.headers.get("User-Agent", "")))
        cnx.commit()
        lead_id = cur.lastrowid
        cnx.close()

        log_event("INFO", "intake_received", lead_id=lead_id,
                  zip=zip_value, niche=niche)

        # 4. Fire dispatch (best-effort; dispatcher retries)
        dispatch_ok, dispatch_resp = fire_dispatch(lead_id, {
            "zip": zip_value,
            "name": name,
            "phone": phone,
            "message": message,
            "niche": niche,
        })
        update_dispatch_attempt(lead_id, dispatch_ok, dispatch_resp)
        if dispatch_ok:
            log_event("EVENT", "dispatch_ok", lead_id=lead_id,
                      response=dispatch_resp[:100])
        else:
            log_event("WARN", "dispatch_deferred", lead_id=lead_id,
                      reason=dispatch_resp[:120])

        # 5. Best-effort mirror to hub (non-blocking conceptually)
        try:
            mirror_to_hub(lead_id, {
                "zip": zip_value,
                "name": name,
                "phone": phone,
                "niche": niche,
                "email": data.get("email"),
            })
        except Exception as e:
            log_event("WARN", "hub_mirror_failed",
                      lead_id=lead_id, err=str(e)[:120])

        # 6. Respond
        body = {
            "ok": True,
            "lead_id": lead_id,
            "dispatch": {
                "delivered": dispatch_ok,
                "will_retry": not dispatch_ok,
            },
            "next_step": "tap_to_call_dispatch",
            "tel": DISPATCH_TEL or None,
            "tel_label": DISPATCH_NAME or "Dispatch",
        }
        self._send(200, json.dumps(body).encode())


# ── Landing page renderer ───────────────────────────────────────────────
def render_landing_page(*, tel: str, dispatch_name: str,
                        allowed_zip_prefixes: list[str],
                        disaster_mode: bool) -> str:
    """High-contrast yellow hazard header, single zip field, tap-to-call."""
    # No fake phone numbers. JavaScript will swap once /health confirms.
    tel_display = "— configure PPL_DISPATCH_TEL —" if not tel else tel
    tel_href = "tel:" + tel if tel else "#"
    area_note = ("Zips served: " + ", ".join(allowed_zip_prefixes)
                 if allowed_zip_prefixes
                 else "All Texas-area zips accepted.")
    disaster_banner = (""
        if not disaster_mode
        else '<div style="background:#5b1a1a;color:#fff;padding:8px 16px;'
             'text-align:center"><strong>PAUSED:</strong> '
             'This PPL is not accepting active-emergency leads right now. '
             'Call your county emergency line for help.</div>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Texas Flood Emergency | Water Removal 24/7</title>
<style>
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: system-ui, -apple-system, sans-serif; color:#111;
       background:#fff; line-height: 1.4 }}
.hazard {{ background:#ffcc00; color:#000; padding:18px 16px; text-align:center;
           font-weight:800; border-bottom:4px solid #000; }}
.hazard .blink {{ animation: blink 1.2s steps(2,end) infinite; }}
@keyframes blink {{ 50% {{ opacity:0.4 }} }}
h1 {{ font-size: 38px; margin: 16px; line-height:1.05;
      font-weight: 900; letter-spacing:-0.5px; }}
.warn {{ background:#5b1a1a; color:#fff; padding:14px 16px;
         margin: 0 0 16px 0; }}
main {{ max-width:680px; margin: 0 auto; padding: 16px; }}
form {{ background:#f4f4f4; padding:18px; border:2px solid #000; }}
label {{ font-weight:700; display:block; margin-bottom:8px; }}
input[type=text] {{ font-size:24px; padding:14px 12px; width:100%;
                    border:2px solid #000; border-radius:4px; }}
button {{ font-size:22px; font-weight:800; padding:18px;
          background:#cc0000; color:#fff; border:0;
          border-radius:4px; width:100%; margin-top:12px; cursor:pointer; }}
button:hover {{ background:#aa0000; }}
.callnow {{ display:block; background:#0057b8; color:#fff; padding:18px;
            text-align:center; font-size:24px; font-weight:800;
            border-radius:4px; text-decoration:none; margin-top:14px; }}
.area {{ font-size:13px; color:#444; margin-top:8px; }}
.bullets {{ padding-left: 18px; }}
.bullets li {{ margin: 6px 0; }}
.fine {{ font-size:11px; color:#555; margin-top:18px; line-height:1.4; }}
</style></head>
<body>
<div class="hazard">
  <div class="blink">⚠ FLASH FLOOD WARNING ⚠ &nbsp;
       KERRVILLE • UVALDE • SABINAL AREA</div>
</div>
{disaster_banner}
<main>
<h1>TEXAS FLOOD EMERGENCY:<br>Local Water Removal<br>Experts On Call 24/7.</h1>
<div class="warn">
  Standing water? Ceiling bulging? Wet carpet and a smell starting? Call
  someone in your county right now. Don't wait — mold starts in 24 hours.
</div>
<form id="intake" autocomplete="off">
  <label for="zip">Enter your ZIP code. We'll ring a local crew.</label>
  <input id="zip" name="zip" inputmode="numeric" pattern="\\d{{5}}"
         maxlength="5" placeholder="5-digit ZIP" required>
  <button type="submit">CALL DISPATCH NOW →</button>
  <div class="area">{area_note}</div>
</form>
<a class="callnow" href="{tel_href}" id="callnow">📞 CALL {dispatch_name}: {tel_display}</a>
<ul class="bullets">
  <li>Water removal &amp; extraction — pumps on the truck, not a wait list</li>
  <li>Ceiling collapse &amp; ceiling drywall tear-out</li>
  <li>Wet carpet pull, pad disposal, subfloor drying</li>
  <li>Sanitizing &amp; mold prevention (mold starts in 24h)</li>
  <li>Insurance paperwork photos and invoice for your claim</li>
</ul>
<div class="fine">
  By submitting, you consent to be contacted about water-removal
  services in your area. This service is Pay-Per-Lead marketing;
  we share your ZIP with a vetted local dispatch. We do not sell
  your data. Texas residents only. Unsubscribe: reply STOP.
</div>
</main>
<script>
document.getElementById('intake').addEventListener('submit', async (e) => {{
  e.preventDefault();
  const zip = document.getElementById('zip').value.trim();
  if (!/^\\d{{5}}$/.test(zip)) {{
    alert('Five digits, please.'); return;
  }}
  const r = await fetch('/v1/ppl/intake', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{ zip, source: 'tx_flood_landing_page',
                            niche: 'texas_flood_2026' }})
  }});
  const j = await r.json();
  if (j.ok) {{
    document.getElementById('callnow').style.display='block';
    document.getElementById('callnow').scrollIntoView({{
      behavior:'smooth', block:'center' }});
  }} else {{
    alert(j.error || 'Could not route. Try calling direct.');
  }}
}});
</script>
</body></html>"""


# ── Server bootstrap ────────────────────────────────────────────────────
def serve():
    init_db()
    log_event("INFO", "ppl_service_starting",
              port=PORT,
              zip_prefixes=list(ZIP_PREFIXES),
              disaster_mode=DISASTER_MODE,
              dispatch_url_configured=bool(DISPATCH_URL),
              dispatch_tel_configured=bool(DISPATCH_TEL),
              mirror_to_hub=MIRROR_TO_HUB,
              hub=HUB)
    t = threading.Thread(target=dispatcher_loop, daemon=True)
    t.start()
    httpd = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log_event("INFO", "ppl_service_stopping")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
