"""BSC USDT settlement listener — watches USDT Transfer events to vault wallet.

Properly parses ERC-20 Transfer(event) topics:
  topic[0] = keccak256("Transfer(address,address,uint256)")
  topic[1] = from address (padded to 32 bytes)
  topic[2] = to address (padded to 32 bytes)
  data = amount (uint256)

Matches incoming USDT to pending si_invoice rows by amount, marks them paid.

Run: python3 -u /root/empire_os/empire_os/bsc_usdt_listener_fixed.py
"""

import os, sys, json, time, subprocess
from datetime import datetime, timezone
import sqlite3 as sq

# ── Config ──────────────────────────────────────────────────────────────────
def _load_env():
    """Load .env file into os.environ (simple parser)."""
    env_path = "/root/empire_os/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v

_load_env()

BSC_RPC = os.environ.get(
    "BSC_RPC",
    "https://rpc.ankr.com/bsc/cfb120f5c350ee1a2cdf8b36177e979da9527fed0fb557e6b17f828b26c11087",
)
BSC_USDT_CONTRACT = os.environ.get(
    "BSC_USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955"
).lower()
BSC_WALLET = os.environ.get(
    "BSC_WALLET_ADDRESS", "0x1339b487046B0ad924a10c20b1791608EA8595a8"
).lower()

DB = "/root/empire_os/empire_os.db"
POLL_INTERVAL = int(os.environ.get("BSC_POLL_INTERVAL", "10"))
BLOCK_BATCH = 1000  # blocks per batch (Ankr premium allows 1000 block range)

USDT_DECIMALS = 18

# ERC-20 Transfer event signature
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df9ab46fe"

print(f"[bsc-usdt] RPC={BSC_RPC}")
print(f"[bsc-usdt] USDT contract={BSC_USDT_CONTRACT}")
print(f"[bsc-usdt] Vault wallet={BSC_WALLET}")

# ── RPC ─────────────────────────────────────────────────────────────────────
def _rpc(method, params):
    import urllib.request, urllib.error
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params
    }).encode()
    url = BSC_RPC
    if not url.endswith("/"):
        url += "/"
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)[:300]}

# ── Helpers ──────────────────────────────────────────────────────────────────
def _addr_from_topic(topic_hex):
    """Extract 20-byte address from 32-byte topic (last 40 hex chars)."""
    if not topic_hex:
        return ""
    topic_hex = topic_hex.lower()
    if topic_hex.startswith("0x"):
        topic_hex = topic_hex[2:]
    if len(topic_hex) >= 64:
        return "0x" + topic_hex[-40:]
    return "0x" + topic_hex.zfill(40)[-40:]

def _hex_to_int(hex_str):
    """Convert hex string to int."""
    if not hex_str:
        return 0
    hex_str = hex_str.lower()
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]
    try:
        return int(hex_str, 16)
    except ValueError:
        return 0

def _get_pending_invoices_by_amount():
    """Load pending invoices from the LIVE tables grouped by
    amount in integer micro-USDC (6dp) for exact matching.

    Sources (2026-08-21):
      - si_ppc_invoices (status='open', amount_usdc)
      - funnel_state   (key_id LIKE 'invoice.deep_%', status='pending',
                        amount_usdc=29) — deep audit invoices
    """
    con = sq.connect(DB, timeout=30)
    con.row_factory = sq.Row
    try:
        c = con.cursor()
        c.execute("PRAGMA busy_timeout=5000")
        invoices = {}

        # si_ppc_invoices may not exist (schema drift) — deep audit flow
        # in funnel_state is the canonical source now.
        try:
            c.execute("""
                SELECT invoice_id, CAST(ROUND(amount_usdc * 1000000) AS INTEGER)
                FROM si_ppc_invoices
                WHERE status = 'open'
                  AND amount_usdc > 0
                ORDER BY created_at ASC
            """)
            for row in c.fetchall():
                inv_id, micro = row[0], row[1]
                if micro not in invoices:
                    invoices[micro] = []
                invoices[micro].append(inv_id)
        except Exception as e:
            print(f"[bsc-usdt] si_ppc_invoices scan skipped: {e}")

        # deep audit invoices from funnel_state (amount fixed at $29)
        try:
            c.execute("""
                SELECT key_id, state_json FROM funnel_state
                WHERE key_id LIKE 'invoice.deep_%'
                   OR key_id LIKE 'invoice.SKU_%'
            """)
            for row in c.fetchall():
                try:
                    state = json.loads(row[1])
                except Exception:
                    continue
                if state.get('status') != 'pending':
                    continue
                amt = float(state.get('amount_usdc') or 0)
                micro = int(round(amt * 1000000))
                inv_id = row[0].split('.', 1)[1]  # strip 'invoice.' prefix
                if micro not in invoices:
                    invoices[micro] = []
                invoices[micro].append(inv_id)
        except Exception as e:
            print(f"[bsc-usdt] funnel_state deep-audit scan skipped: {e}")

        # ── Seat subscriptions (select-serve / auto_onboard) ──────────────
        # These mints a BSC USDT link with memo empire-os:<tenant>:<plan>:<id>
        # and status='awaiting_payment'. Match by exact amount so a verified
        # on-chain USDT deposit activates the seat (otherwise buyer pays but
        # the lane never seats — silent revenue leak).
        try:
            c.execute(
                """SELECT subscription_id, CAST(ROUND(price_cents) AS INTEGER)
                   FROM si_subscription
                   WHERE status='awaiting_payment'
                     AND payment_method='usdc'
                     AND price_cents > 0""")
            for sub_id, cents in c.fetchall():
                micro = int(round(cents * 10000))  # price_cents*1e4 = micro-USDC
                if micro not in invoices:
                    invoices[micro] = []
                invoices[micro].append(f"seat:{sub_id}")
        except Exception as e:
            print(f"[bsc-usdt] seat-subscription scan skipped: {e}")

        # ── MRR subscription invoices (si_invoice, status='issued') ──────
        # Founder/silver/enterprise tenants pay via /pay/<memo> page.
        # Match incoming USDT by exact cents so invoice flips to paid.
        try:
            c.execute(
                """SELECT invoice_id, CAST(ROUND(amount_cents) AS INTEGER)
                   FROM si_invoice
                   WHERE status='issued'
                     AND amount_cents > 0""")
            for inv_id, cents in c.fetchall():
                micro = int(round(cents * 10000))  # cents*1e4 = micro-USDC
                if micro not in invoices:
                    invoices[micro] = []
                invoices[micro].append(f"mrr:{inv_id}")
        except Exception as e:
            print(f"[bsc-usdt] si_invoice scan skipped: {e}")

        return invoices
    finally:
        con.close()

def _deliver_sku(c, sku, email, invoice_id, amt, niche="", metro="", url=""):
    """Enqueue delivery email for a paid SKU order into si_outbox.

    deep_intel_report: runs the 25+ check deep audit engine + attaches PDF.
    lead_pack_50/250: exports top Omega-scored leads for niche+metro as CSV
    attachment (base64). Sent via Brevo by the running mail-sender worker
    (approval pre-seeded: aprv-sku-delivery-auto).
    """
    from empire_os.mail_sender import _brevo_api_send
    subject = f"[Empire AI] Your {sku.replace('_', ' ').title()} — Order {invoice_id}"
    html = ""
    attachments = []
    try:
        if sku == "deep_intel_report" and url:
            from empire_os.deep_audit import run_deep_audit, generate_deep_pdf
            import base64, shutil
            result = run_deep_audit(url)
            result["url"] = url
            result["niche"] = niche or "general"
            pdf_dir = Path("/srv/aeo/audits")
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_name = f"{invoice_id}.pdf"
            shutil.copy2(generate_deep_pdf(result), str(pdf_dir / pdf_name))
            dl_url = f"https://empire-ai.co.uk/audits/{pdf_name}"
            html = (
                f"<h2 style='color:#0D47A1'>Deep Intel Report — {url}</h2>"
                f"<p><b style='color:#39FF14'>Score: {result['score']}/100 "
                f"({result['grade']})</b></p>"
                f"<p>{len(result.get('checks', []))} checks run. Full "
                f"90-day attack plan attached + hosted:</p>"
                f"<p><a href='{dl_url}'>{dl_url}</a></p>")
            subject = (f"[Empire AI] Deep Intel Report — Score {result['score']}/100 "
                       f"({result['grade']}) — {url}")
        elif sku.startswith("serp_sweep"):
            # SERP Intent Sweep: run live serper discovery + Omega scoring,
            # then ship everything found for this niche+metro as CSV.
            import base64, csv, io
            want = 250 if "250" in sku else 100
            from empire_os.lead_engine import serp_discovery
            sweeps = max(1, want // 10)
            added_total = 0
            for _ in range(sweeps):
                st = serp_discovery.discover(niche or "roofing",
                                             metro or "Nashville", 10)
                added_total += st.get("added", 0)
            con2 = sq.connect(DB, timeout=30)
            rows = con2.execute(
                "SELECT business_name, website, notes, omega_score FROM crm_leads "
                "WHERE source='serp_discovery' AND (?='' OR niche=?) "
                "AND (?='' OR metro=?) "
                "ORDER BY COALESCE(omega_score,0) DESC LIMIT ?",
                (niche, niche, metro, metro, want)).fetchall()
            con2.close()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["business_name", "website", "intent_notes",
                        "omega_score"])
            for r in rows:
                w.writerow(r)
            attachments = [{
                "name": f"{invoice_id}.csv",
                "content": base64.b64encode(
                    buf.getvalue().encode()).decode(),
            }]
            html = (f"<h2 style='color:#0D47A1'>SERP Intent Sweep — {len(rows)} "
                    f"businesses</h2><p>Google SERP sweep complete: "
                    f"{added_total} new leads added for {niche or 'any'}/"
                    f"{metro or 'any'}, all Omega-scored. CSV attached.</p>"
                    f"<p style='color:#39FF14'>Intent signals flagged "
                    f"(hiring/expansion/new-location) in notes column.</p>")
        elif sku.startswith("lead_pack"):
            import base64, csv, io
            want = 250 if "250" in sku else 50
            con2 = sq.connect(DB, timeout=30)
            rows = con2.execute(
                "SELECT business_name, phone, email, website, city, state, "
                "omega_score FROM lane_leads "
                "WHERE (?='' OR sub_niche LIKE '%'||?||'%') "
                "AND (?='' OR city LIKE '%'||?||'%') "
                "AND COALESCE(email,'')!='' "
                "ORDER BY omega_score DESC LIMIT ?",
                (niche, niche, metro, metro, want)).fetchall()
            con2.close()
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["business_name", "phone", "email", "website",
                        "city", "state", "omega_score"])
            for r in rows:
                w.writerow(r)
            attachments = [{
                "name": f"{invoice_id}.csv",
                "content": base64.b64encode(
                    buf.getvalue().encode()).decode(),
            }]
            html = (f"<h2 style='color:#0D47A1'>Your Lead Pack — {len(rows)} "
                    f"exclusive leads</h2><p>Omega-scored, enrichment-complete. "
                    f"CSV attached ({want} ordered, niche={niche or 'any'}, "
                    f"metro={metro or 'any'}).</p>"
                    f"<p style='color:#39FF14'>First-mover rule: these are "
                    f"exclusive — work them within 72 hours.</p>")
        elif sku.startswith("seo_"):
            # EmpireSEO product: real engine output shipped as JSON/HTML.
            import json as _json
            import sys as _sys
            _sys.path.insert(0, "/root/empire_os")
            from empire_seo import audit_site, brief as seo_brief
            if sku == "seo_audit_report" and url:
                a = audit_site(url, max_pages=5)
                html = (
                    f"<h2 style='color:#0D47A1'>SEO Audit Report — {url}</h2>"
                    f"<p><b style='color:#39FF14'>Score: {a.get('avg_score')}/100</b></p>"
                    f"<p>Pages audited: {a.get('pages_audited')}</p>"
                    f"<p><b>Issues found:</b></p><ul>"
                    + "".join(f"<li>{i}</li>" for i in a.get("issues", []))
                    + "</ul>"
                    f"<p>Page detail (JSON): "
                    f"<code>{_json.dumps(a.get('pages', [])[:3])[:600]}</code></p>")
            elif sku == "seo_content_brief":
                br = seo_brief(niche or "roofing", metro or "Dallas")
                bb = br["brief"]
                html = (
                    f"<h2 style='color:#0D47A1'>SEO Content Brief — "
                    f"{niche or 'roofing'} / {metro or 'Dallas'}</h2>"
                    f"<p><b>Title:</b> {bb['title']}</p>"
                    f"<p><b>Meta:</b> {bb['meta_description']}</p>"
                    f"<p><b>H1:</b> {bb['h1']}</p>"
                    f"<p><b>Sections:</b> " +
                    " | ".join(s["h2"] for s in bb["sections"]) + "</p>"
                    f"<p><b>Real demand keywords:</b> "
                    f"{', '.join(bb['demand_keywords'][:12])}</p>")
            else:
                html = (f"<h2 style='color:#0D47A1'>Order {invoice_id} confirmed</h2>"
                        f"<p>SKU <b>{sku}</b> paid (${amt:.2f} USDT). Our team "
                        f"fulfills within 24h.</p>")
        elif sku == "cortex_blueprint_pack":
            # Cortex Intelligence product: niche blueprint + niche heat scores.
            import json as _json
            import sys as _sys
            _sys.path.insert(0, "/root/empire_os")
            try:
                from cortex_api import _fetch_blueprint, _niche_heat
                bp = _fetch_blueprint(niche or "b2b", limit=3) or {}
                heat = _niche_heat(niche or "b2b", metro or "")
                bps = bp.get("blueprints", [])
                if bps:
                    html = (
                        f"<h2 style='color:#0D47A1'>Cortex Blueprint Pack — "
                        f"{niche or 'b2b'}</h2>"
                        f"<p><b style='color:#39FF14'>Niche heat score: {heat}/100</b></p>"
                        f"<p><b>Blueprints included:</b> {bp.get('count')}</p>")
                    for b in bps:
                        html += (
                            f"<p><b>{b['blueprint_id']}</b> ({b['campaign_type']})</p>"
                            f"<p>Visual DNA: <code>{_json.dumps(b['visual_dna'])[:300]}</code></p>"
                            f"<p>Script DNA: <code>{_json.dumps(b['script_dna'])[:300]}</code></p>")
                    html += ("<p style='color:#39FF14'>Deploy via Cortex API "
                             "or Empire OS agents.</p>")
                else:
                    html = (f"<h2 style='color:#0D47A1'>Cortex Blueprint Pack — "
                            f"{niche or 'b2b'}</h2>"
                            f"<p><b>Niche heat score: {heat}/100</b></p>"
                            f"<p>No prebuilt blueprint for this niche yet. Our team "
                            f"generates one within 24h and ships it to this address.</p>")
            except Exception as _ce:
                html = (f"<h2 style='color:#0D47A1'>Cortex Blueprint Pack — {niche or 'b2b'}</h2>"
                        f"<p>Order {invoice_id} confirmed (${amt:.2f} USDT). "
                        f"Fulfillment within 24h. Ref: {_ce}</p>")
        else:
            html = (f"<h2 style='color:#0D47A1'>Order {invoice_id} confirmed</h2>"
                    f"<p>SKU <b>{sku}</b> paid (${amt:.2f} USDT). Our team "
                    f"fulfills within 24h.</p>")
        out = _brevo_api_send(
            to=email, subject=subject, body="See HTML version.",
            html_body=html)
        print(f"[bsc-usdt] SKU delivery sent {invoice_id} -> {email} "
              f"({out.get('status', out)})")
    except Exception as e:
        print(f"[bsc-usdt] _deliver_sku error {invoice_id}: {e}")
        try:
            c.execute(
                "INSERT INTO si_outbox (to_email, subject, body, lane, tier, "
                "source, status, meta_json, recipient_kind, approval_ref, "
                "provider_message_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (email, subject,
                 f"Order {invoice_id} ({sku}) paid — delivery follow-up "
                 f"required (auto-mail failed: {str(e)[:200]})",
                 "revenue", "paid", "sku_delivery", "pending", "{}", "buyer",
                 "aprv-sku-delivery-auto", f"sku_{invoice_id}"))
        except Exception as e2:
            print(f"[bsc-usdt] outbox fallback failed {invoice_id}: {e2}")


def _mark_paid(invoice_id, tx_hash, amount_usdt):
    """Mark an invoice as paid: si_ppc_invoices (live table) and/or
    funnel_state deep audit invoice."""
    ts_iso = datetime.now(timezone.utc).isoformat()
    marked = 0
    con = sq.connect(DB, timeout=30)
    con.row_factory = sq.Row
    try:
        c = con.cursor()
        c.execute("PRAGMA busy_timeout=5000")
        # si_ppc_invoices may not exist (schema drift) — don't let it
        # block the funnel_state deep-audit flip below.
        try:
            c.execute(
                "UPDATE si_ppc_invoices SET status='paid', "
                "paid_at=?, metadata=json_set(COALESCE(metadata,'{}'),'$.paid_method','usdt_bsc') "
                "WHERE invoice_id=? AND status='open'",
                (ts_iso, f"bsc_usdt:{tx_hash}", invoice_id),
            )
            marked += max(c.rowcount, 0)
        except Exception as e:
            print(f"[bsc-usdt] si_ppc_invoices update skipped: {e}")
        # deep audit invoice in funnel_state?
        c.execute(
            "SELECT state_json FROM funnel_state WHERE key_id=?",
            (f"invoice.{invoice_id}",),
        )
        row = c.fetchone()
        if row:
            try:
                state = json.loads(row[0])
                if state.get('status') == 'pending':
                    state['status'] = 'paid'
                    state['paid_tx'] = tx_hash
                    state['paid_at'] = ts_iso
                    c.execute(
                        "UPDATE funnel_state SET state_json=?, updated_at=? "
                        "WHERE key_id=?",
                        (json.dumps(state), time.time(),
                         f"invoice.{invoice_id}"),
                    )
                    marked += 1
            except Exception as e:
                print(f"[bsc-usdt] funnel_state update failed {invoice_id}: {e}")
        # seat subscription activation (select-serve / auto_onboard)
        if str(invoice_id).startswith("seat:"):
            sub_id = invoice_id.split(":", 1)[1]
            try:
                c.execute(
                    "SELECT tenant_id, niche, plan FROM si_subscription "
                    "WHERE subscription_id=? AND status='awaiting_payment'",
                    (sub_id,))
                row = c.fetchone()
                if row:
                    tenant_id, niche, plan = row[0], row[1], row[2]
                    from empire_os import auto_onboard as _ao
                    tier = (plan or "bronze").replace("lane_", "")
                    c.execute(
                        "UPDATE si_subscription SET status='active', "
                        "started_at=datetime('now'), "
                        "current_period_end=datetime('now','+30 days') "
                        "WHERE subscription_id=?", (sub_id,))
                    _ao._direct_seat(con, niche or "buyer", niche or "buyer",
                                    tier, 0.0, 0.0, tenant_id=tenant_id)
                    c.execute(
                        "UPDATE si_tenant SET status='active' WHERE tenant_id=?",
                        (tenant_id,))
                    marked += 1
                    print(f"[bsc-usdt] SEAT ACTIVATED {sub_id} tenant={tenant_id} tier={tier}")
            except Exception as e:
                print(f"[bsc-usdt] seat activation failed {sub_id}: {e}")
        # MRR subscription invoice flip (founder/silver/enterprise /pay flow)
        if str(invoice_id).startswith("mrr:"):
            mrr_inv = invoice_id.split(":", 1)[1]
            try:
                c.execute(
                    "UPDATE si_invoice SET status='paid', paid_method='usdt', "
                    "paid_at=? WHERE invoice_id=? AND status='issued'",
                    (ts_iso, mrr_inv))
                if c.rowcount:
                    marked += 1
                    print(f"[bsc-usdt] MRR INVOICE PAID {mrr_inv} (${c.execute('SELECT amount_cents FROM si_invoice WHERE invoice_id=?', (mrr_inv,)).fetchone()[0]/100:.2f})")
            except Exception as e:
                print(f"[bsc-usdt] mrr invoice flip failed {mrr_inv}: {e}")
        # SKU product order (deep_intel_report / lead packs) — mark paid
        # in funnel_state and enqueue delivery email via si_outbox.
        if str(invoice_id).startswith("SKU_"):
            try:
                c.execute(
                    "SELECT state_json FROM funnel_state WHERE key_id=?",
                    (f"invoice.{invoice_id}",))
                row = c.fetchone()
                if row:
                    state = json.loads(row[0])
                    if state.get("status") == "pending":
                        state["status"] = "paid"
                        state["paid_tx"] = tx_hash
                        state["paid_at"] = ts_iso
                        c.execute(
                            "UPDATE funnel_state SET state_json=?, updated_at=? "
                            "WHERE key_id=?",
                            (json.dumps(state), time.time(),
                             f"invoice.{invoice_id}"))
                        marked += 1
                        sku = state.get("sku", "")
                        email = state.get("email", "")
                        amt = float(state.get("amount_usdc") or 0)
                        print(f"[bsc-usdt] SKU ORDER PAID {invoice_id} "
                              f"sku={sku} ${amt:.2f} -> {email}")
                        _deliver_sku(c, sku, email, invoice_id, amt,
                                     state.get("niche", ""),
                                     state.get("metro", ""),
                                     state.get("url", ""))
            except Exception as e:
                print(f"[bsc-usdt] sku delivery failed {invoice_id}: {e}")
        con.commit()
        return marked
    except Exception as e:
        print(f"[bsc-usdt] ERROR marking paid {invoice_id}: {e}")
        return 0
    finally:
        con.close()

# ── Get logs via eth_getLogs ─────────────────────────────────────────────────
def _get_transfer_logs(from_block, to_block):
    """Get USDT Transfer events to our vault wallet in block range.
    
    Uses eth_getBlockByNumber + manual transaction scan as fallback
    when public RPCs block eth_getLogs.
    """
    # Try eth_getLogs first
    vault_padded = "0x" + BSC_WALLET[2:].lower().zfill(64)
    params = [{
        "address": BSC_USDT_CONTRACT,
        "topics": [TRANSFER_TOPIC, None, vault_padded],
        "fromBlock": hex(from_block),
        "toBlock": hex(to_block),
    }]
    resp = _rpc("eth_getLogs", params)
    if "error" not in resp and isinstance(resp.get("result"), list):
        logs = resp["result"]
        transfers = []
        for log in logs:
            tx_hash = log.get("transactionHash", "")
            block_num = _hex_to_int(log.get("blockNumber", "0"))
            topics = log.get("topics", [])
            data = log.get("data", "0x")
            if len(topics) < 3:
                continue
            from_addr = _addr_from_topic(topics[1])
            to_addr = _addr_from_topic(topics[2])
            amount_raw = _hex_to_int(data)
            amount_usdt = amount_raw / (10 ** USDT_DECIMALS)
            amount_cents = int(round(amount_usdt * 100))
            transfers.append({
                "tx_hash": tx_hash, "block": block_num,
                "from": from_addr, "to": to_addr,
                "amount_raw": amount_raw,
                "amount_usdt": amount_usdt, "amount_cents": amount_cents,
            })
        return transfers

    # Fallback: scan blocks transaction-by-transaction
    # Get each block with full transaction objects, then get receipts
    # for any tx going to USDT contract
    transfers = []
    for block_num in range(from_block, to_block + 1):
        resp = _rpc("eth_getBlockByNumber", [hex(block_num), True])
        if "error" in resp or "result" not in resp:
            continue
        block = resp["result"]
        if not block:
            continue
        for tx_obj in block.get("transactions", []):
            to_addr = (tx_obj.get("to") or "").lower()
            if to_addr != BSC_USDT_CONTRACT:
                continue
            # This is a USDT transfer — get receipt for log events
            tx_hash = tx_obj.get("hash", "")
            resp2 = _rpc("eth_getTransactionReceipt", [tx_hash])
            if "error" in resp2 or "result" not in resp2:
                continue
            receipt = resp2["result"]
            for log in receipt.get("logs", []):
                log_addr = (log.get("address") or "").lower()
                if log_addr != BSC_USDT_CONTRACT:
                    continue
                topics = log.get("topics", [])
                if len(topics) < 3:
                    continue
                # Check topic0 matches Transfer event
                if topics[0].lower() != TRANSFER_TOPIC:
                    continue
                to_addr_log = _addr_from_topic(topics[2])
                if to_addr_log != BSC_WALLET:
                    continue
                from_addr = _addr_from_topic(topics[1])
                amount_raw = _hex_to_int(log.get("data", "0x"))
                amount_usdt = amount_raw / (10 ** USDT_DECIMALS)
                amount_cents = int(round(amount_usdt * 100))
                transfers.append({
                    "tx_hash": tx_hash, "block": block_num,
                    "from": from_addr, "to": to_addr_log,
                    "amount_raw": amount_raw,
                    "amount_usdt": amount_usdt, "amount_cents": amount_cents,
                })
    return transfers

# ── Main loop ────────────────────────────────────────────────────────────────
def listen_loop():
    print(f"[bsc-usdt] starting listen loop")

    # Get current block
    resp = _rpc("eth_blockNumber", [])
    if "error" in resp:
        print(f"[bsc-usdt] FATAL: cannot get block number: {resp.get('error')}")
        return

    last_block = int(resp.get("result", "0x0"), 16)
    print(f"[bsc-usdt] starting from block {last_block}")

    # State file to persist last scanned block
    STATE_FILE = "/root/feedback/bsc_usdt_state.json"
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
            saved_block = state.get("last_block", 0)
            if saved_block > last_block - 100000:  # within ~3 days
                last_block = saved_block
                print(f"[bsc-usdt] resuming from saved block {last_block}")
    except Exception:
        pass

    while True:
        try:
            resp = _rpc("eth_blockNumber", [])
            if "error" in resp:
                print(f"[bsc-usdt] block number error: {resp.get('error')}")
                time.sleep(POLL_INTERVAL)
                continue

            current_block = int(resp.get("result", "0x0"), 16)

            if current_block <= last_block:
                time.sleep(POLL_INTERVAL)
                continue

            # Process in batches
            end_block = min(last_block + BLOCK_BATCH, current_block)

            print(f"[bsc-usdt] scanning blocks {last_block+1} to {end_block} (current={current_block})")

            transfers = _get_transfer_logs(last_block + 1, end_block)

            if transfers:
                print(f"[bsc-usdt] found {len(transfers)} USDT Transfer(s) to vault")

                # Load pending invoices
                pending = _get_pending_invoices_by_amount()
                if pending:
                    for tx in transfers:
                        micro = int(round(tx["amount_usdt"] * 1000000))
                        if micro in pending and pending[micro]:
                            # Match! Mark the oldest invoice with this amount as paid
                            inv_id = pending[micro].pop(0)
                            rows = _mark_paid(inv_id, tx["tx_hash"], tx["amount_usdt"])
                            if rows:
                                print(
                                    f"[bsc-usdt] PAID invoice {inv_id} "
                                    f"amount=${tx['amount_usdt']:.2f} "
                                    f"tx={tx['tx_hash'][:16]}..."
                                )
                            else:
                                # Put it back if update failed
                                pending[micro].insert(0, inv_id)
                        else:
                            print(
                                f"[bsc-usdt] received ${tx['amount_usdt']:.2f} "
                                f"({micro} micro) from {tx['from'][:10]}... "
                                f"but no matching pending invoice"
                            )
                else:
                    print(f"[bsc-usdt] {len(transfers)} transfer(s) but no pending invoices")

            last_block = end_block

            # Save state
            try:
                with open(STATE_FILE, "w") as f:
                    json.dump({"last_block": last_block}, f)
            except Exception:
                pass

            if current_block > end_block:
                # More blocks to process — don't sleep
                continue

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("[bsc-usdt] shutting down")
            break
        except Exception as e:
            print(f"[bsc-usdt] loop error: {e}")
            time.sleep(15)


if __name__ == "__main__":
    print(f"[bsc-usdt] BSC USDT Listener (fixed) starting at {datetime.now(timezone.utc).isoformat()}")
    listen_loop()
