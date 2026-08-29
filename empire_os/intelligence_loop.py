#!/usr/bin/env python3
"""
Empire OS v3 — Intelligence-Enhanced Revenue Loop
=================================================
Wires together:
- AI Intelligence (ai_intelligence.py) for lead analysis + predictive revenue
- Lead Sniper for high-intent discovery
- Cortex for strategic direction
- A2A buyer matching (mcp_lead_server) for semantic matching
- Delivery pipeline (lead_deliverer) with intelligent routing
- Waterfall for multi-buyer optimization

Run as a daemon or via cron every 60s.
"""

import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os.ai_intelligence import (
    analyze_page,
    predict_revenue,
    match_buyers,
    process_lead,
    PageAnalysis,
    PredictiveRevenue,
    BuyerMatch,
)
from empire_os.agent_core import OllamaClient
from empire_os.pinecone_intel import semantic_buyer_match
from empire_os.pinecone_client import get_client
DB = "/root/empire_os/empire_os.db"
LOG_DIR = Path("/root/feedback/intelligence_loop")
LOG_DIR.mkdir(parents=True, exist_ok=True)

HUB_URL = "http://127.0.0.1:8080"
TICK_INTERVAL = int(os.environ.get("INTELLIGENCE_TICK", "60"))
BATCH_SIZE = int(os.environ.get("INTELLIGENCE_BATCH", "50"))

si = None  # Lazy init when LLM available
ai_client = None

def get_synthetic_intelligence():
    """Get or create SyntheticIntelligence instance with available LLM."""
    global si, ai_client
    if si is not None:
        return si
    if ai_client is None:
        try:
            ai_client = OllamaClient()
        except Exception:
            ai_client = None
    if ai_client is not None:
        # SyntheticIntelligence class doesn't exist - skip for now
        si = None
    return si


def log(level, msg, **fields):
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "msg": msg,
        **fields,
    }
    with open(LOG_DIR / "intelligence_loop.jsonl", "a") as f:
        f.write(json.dumps(event) + "\n")
    if level in ("ERROR", "WARN", "CYCLE"):
        print(json.dumps(event))


def get_pending_leads(limit: int = BATCH_SIZE):
    """Fetch leads stuck in 'pending' that need intelligent routing."""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    rows = cur.execute(
        """
        SELECT id, omega_score, omega_tier, buyer_id
        FROM lane_leads
        WHERE (buyer_id IS NULL OR buyer_id = '')
        ORDER BY omega_score DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_active_buyers():
    """Get buyers with payment methods ready to receive leads."""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    
    # Get all active buyers from outreach with their wallet addresses
    buyers = cur.execute(
        """
        SELECT b.prospect_id, b.niche, b.metro, b.wallet, b.payout_per_lead,
               b.endpoint_url, b.active
        FROM si_buyer_outreach b
        WHERE b.active = 1
          AND b.prospect_id IS NOT NULL
          AND b.prospect_id != ''
        """
    ).fetchall()
    
    # Build wallet -> payment_method lookup for crypto (USDT) buyers only
    wallet_payments = {}
    for row in cur.execute("SELECT prospect_id, wallet, payout_per_lead, endpoint_url FROM si_buyer_outreach WHERE active=1 AND wallet IS NOT NULL AND wallet != ''"):
        wallet_payments[row["prospect_id"]] = {
            "processor": "usdt_bsc",
            "wallet": row["wallet"],
            "payout_per_lead": row["payout_per_lead"],
            "endpoint_url": row["endpoint_url"]
        }
    
    con.close()
    
    # All active buyers with prospect_id are valid
    result = []
    for b in buyers:
        bdict = dict(b)
        bdict["payment_method"] = {"processor": "usdt_bsc", "wallet": b["prospect_id"]}
        result.append(bdict)
    
    return result


def enrich_lead_with_ai(lead: dict) -> dict:
    """Run AI intelligence on a lead for predictive revenue + strategy."""
    content = f"{lead.get('niche', '')} {lead.get('sub_niche', '')} {lead.get('metro', '')} score:{lead.get('omega_score', 0)}"
    
    # Use the complete process_lead pipeline
    result = process_lead(
        domain=lead.get("niche", "unknown"),
        metro=lead.get("metro", "UNKNOWN"),
        content=content,
        buyers=[],
        market_context={},
    )
    
    lead.update({
        "ai_analysis": result.get("analysis", {}),
        "predicted_revenue": result.get("revenue_prediction", {}).get("expected_revenue", 0),
        "p_close": result.get("revenue_prediction", {}).get("p_close", 0),
        "omega_tier_ai": result.get("omega_tier", {}).get("tier", "D"),
        "recommended_strategy": result.get("revenue_prediction", {}).get("recommended_strategy", "ignore"),
        "priority_score": result.get("revenue_prediction", {}).get("priority_score", 0),
    })
    return lead


def match_buyer_intelligently(lead: dict, buyers: list) -> dict | None:
    """Use AI + semantic matching to find best buyer."""
    if not buyers:
        return None
    
    # First try Pinecone semantic matching (vector similarity + metadata filtering)
    try:
        with get_client() as client:
            semantic_match = semantic_buyer_match(lead, client=client)
        if semantic_match:
            # Verify the matched buyer is in our active buyers list
            buyer_ids = {b["prospect_id"] for b in buyers}
            if semantic_match.get("buyer_id") in buyer_ids:
                # Find full buyer record
                for b in buyers:
                    if b["prospect_id"] == semantic_match["buyer_id"]:
                        log("INFO", "semantic_buyer_match", lead_id=lead["id"], buyer=semantic_match["buyer_id"])
                        return b
    except Exception as e:
        log("WARN", "semantic_match_failed", error=str(e))
    
    # Fallback: Simple rule-based first pass: niche + metro match with normalization
    niche = lead.get("niche", "").lower().replace("_", " ")
    sub_niche = lead.get("sub_niche", "").lower().replace("_", " ")
    metro = lead.get("metro", "").lower()
    state = lead.get("state", "").lower()
    
    # Niche mapping for cross-matching
    niche_aliases = {
        "general_contractor": ["general contractor", "contractor", "construction", "build", "remodel", "renovation"],
        "plumbing": ["plumbing", "plumb"],
        "roof_repair": ["roof repair", "roofing", "roof"],
        "residential_roofing": ["roofing", "roof", "residential roofing"],
        "water_damage_restoration": ["water damage", "restoration", "flood", "mold"],
        "hvac": ["hvac", "heating", "cooling", "air conditioning"],
        "solar": ["solar"],
        "weight_loss": ["weight loss", "weight_loss"],
        "roofing": ["roofing", "roof"],
    }
    
    # Find all relevant niche terms for this lead
    lead_niche_terms = set([niche, sub_niche])
    for key, aliases in niche_aliases.items():
        if key in lead_niche_terms or any(a in lead_niche_terms for a in aliases):
            lead_niche_terms.update(aliases)
            lead_niche_terms.add(key)
    
    scored = []
    for b in buyers:
        score = 0
        buyer_niche = b.get("niche", "").lower()
        buyer_metro = b.get("metro", "").lower()
        
        # Check niche match with aliases
        niche_match = False
        for term in lead_niche_terms:
            if term in buyer_niche:
                niche_match = True
                break
        
        if niche_match:
            score += 10
        if metro and metro in buyer_metro:
            score += 5
        elif state and state in buyer_metro:
            score += 3
        score += b.get("payout_per_lead", 0) / 10  # prefer higher payout
        
        scored.append((score, b))
    
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None


def deliver_lead(lead: dict, buyer: dict) -> bool:
    """POST lead to buyer webhook with HMAC + record in buyer_leads.
    Primary: email delivery (works without webhook).
    Fallback: webhook if endpoint_url configured and email fails."""
    import hmac
    import hashlib
    
    # Ensure we have a valid prospect_id
    prospect_id = buyer.get("prospect_id") or buyer.get("id")
    if not prospect_id:
        log("WARN", "lead_delivery_skipped_no_prospect_id", lead_id=lead["id"])
        return False
    
    payload = {
        "buyer_id": prospect_id,
        "lane_lead_id": lead["id"],
        "prospect_id": prospect_id,
        "niche": "",
        "sub_niche": lead.get("sub_niche", ""),
        "metro": lead.get("metro", ""),
        "tier": lead.get("omega_tier", ""),
        "match_score": 0,
        "payout_usd": buyer.get("payout_per_lead", 0),
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    
    body = json.dumps(payload).encode()
    api_key = prospect_id  # Use prospect_id as HMAC key
    sig = hmac.new(api_key.encode(), body, hashlib.sha256).hexdigest()
    
    # PRIMARY: Email delivery (works without webhook)
    email_success = False
    email = buyer.get("email") or buyer.get("contact_email")
    if email:
        try:
            # Build lead email
            subject = f"New {lead.get('niche', 'lead')} lead for {lead.get('metro', 'your area')}"
            
            email_body = f"""
New lead delivered via Empire OS

Lead Details:
- Name: {lead.get('name', 'N/A')}
- Phone: {lead.get('phone', 'N/A')}
- Email: {lead.get('email', 'N/A')}
- Niche: {lead.get('niche', 'N/A')}
- Sub-niche: {lead.get('sub_niche', 'N/A')}
- Metro: {lead.get('metro', 'N/A')}
- State: {lead.get('state', 'N/A')}
- Omega Score: {lead.get('omega_score', 'N/A')}
- Omega Tier: {lead.get('omega_tier', 'N/A')}
- Details: {lead.get('details', 'N/A')}

Payout: ${buyer.get('payout_per_lead', 0):.2f} per lead
Lead ID: {lead.get('id', 'N/A')}

Log into your Empire OS buyer portal to accept/decline.
            """.strip()
            
            # Use mail_sender's _send function
            from empire_os.mail_sender import _send
            result = _send(email, subject, email_body)
            email_success = result.get("ok", False)
            if email_success:
                endpoint_status = "email_sent"
                endpoint_response = "lead delivered via email"
            else:
                endpoint_status = "email_failed"
                endpoint_response = json.dumps(result)
        except Exception as e:
            endpoint_status = "email_error"
            endpoint_response = str(e)[:200]
            email_success = False
    else:
        endpoint_status = "no_email"
        endpoint_response = "buyer has no email configured"
        email_success = False
    
    # FALLBACK: Webhook if email failed and endpoint configured
    webhook_success = False
    if not email_success:
        endpoint_url = buyer.get("endpoint_url", "")
        if endpoint_url:
            req = urllib.request.Request(
                endpoint_url,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Empire-OS-Signature": sig,
                    "X-Empire-OS-Lead-Id": str(lead["id"]),
                    "X-Empire-OS-Event": "lead.delivered",
                },
                method="POST",
            )
            
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    webhook_success = resp.status == 200
                    endpoint_status = f"http_{resp.status}"
                    endpoint_response = resp.read().decode()[:200]
            except Exception as e:
                webhook_success = False
                endpoint_status = "network_error"
                endpoint_response = str(e)[:200]
        else:
            endpoint_status = "no_webhook"
            endpoint_response = "no endpoint_url configured"
            webhook_success = False
    
    success = email_success or webhook_success
    
    # Record in buyer_leads
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(
        """
        INSERT INTO buyer_leads
        (buyer_id, lane_lead_id, prospect_id, niche, metro, omega_tier,
         match_score, payout_usd, endpoint_status, endpoint_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            prospect_id,
            lead["id"],
            prospect_id,
            "",
            lead.get("metro", ""),
            lead.get("omega_tier", ""),
            0,
            buyer.get("payout_per_lead", 0),
            endpoint_status,
            endpoint_response,
        ),
    )
    
    # Update lane_leads status
    new_status = "delivered" if success else "pending"  # keep pending on failure for retry
    cur.execute(
        "UPDATE lane_leads SET status = ?, buyer_id = ? WHERE id = ?",
        (new_status, prospect_id, lead["id"]),
    )
    
    # Create si_ppc_invoice on successful delivery (for settlement bridge)
    if success:
        import uuid
        import time
        ts = int(time.time())
        amount_cents = int(round(buyer.get("payout_per_lead", 0) * 100))
        payout_usd = buyer.get("payout_per_lead", 0)
        niche = lead.get("niche", "") or ""
        metro = lead.get("metro", "") or ""
        prospect_id_lead = lead.get("prospect_id", "") or ""
        
        invoice_id = f"inv_lead_{lead['id']}_{ts}"
        charge_id = f"chg_lead_{lead['id']}_{ts}"
        head = f"lead_delivery:{niche}:{metro}"
        
        cur.execute("""
            INSERT INTO si_ppc_invoices
            (invoice_id, charge_id, buyer_id, head, lead_id, amount_cents, amount_usdc, status, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)
        """, (invoice_id, charge_id, prospect_id, head, lead["id"], amount_cents, payout_usd,
              json.dumps({"source": "intelligence_loop", "lead_id": lead["id"], "prospect_id": prospect_id_lead}), 
              datetime.now(timezone.utc).isoformat()))
        
        cur.execute("""
            INSERT INTO si_charges
            (charge_id, buyer_id, prospect_id, processor, customer_ref, payment_ref, head, reason, amount_cents, currency, status, processor_response, attempt_count, created_at)
            VALUES (?, ?, ?, 'usdt_bsc', ?, ?, ?, ?, ?, 'USDT', 'pending', ?, 1, ?)
        """, (charge_id, prospect_id, prospect_id, invoice_id, head, f"Settlement for lead {lead['id']} ({niche}/{metro})",
              amount_cents, json.dumps({"source": "intelligence_loop", "lead_id": lead["id"]}), datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
        
        cur.execute("UPDATE buyer_leads SET settlement_status='invoiced', invoice_id=? WHERE lane_lead_id=?",
                     (invoice_id, lead["id"]))
    
    con.commit()
    con.close()
    
    log("INFO" if success else "WARN", "lead_delivery",
        lead_id=lead["id"], buyer=prospect_id,
        status=endpoint_status, payout=buyer.get("payout_per_lead"))
    
    return success
    buyers_sorted = sorted(buyers, key=lambda b: b.get("payout_per_lead", 0), reverse=True)
    
    for buyer in buyers_sorted:
        if deliver_lead(lead, buyer):
            return [buyer]  # success, stop waterfall
        # on failure, continue to next buyer
    return []  # all failed


def update_lead_status(lead_id: int, status: str, notes: str = ""):
    """Record funnel event in si_funnel_event."""
    con = sqlite3.connect(DB)
    cur = con.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """
        INSERT INTO si_funnel_event (prospect_id, from_state, to_state, actor, notes, occurred_at, created_at)
        VALUES (?, 'pending', ?, 'intelligence_loop', ?, ?, ?)
        """,
        (f"lead:{lead_id}", status, notes, now, now),
    )
    con.commit()
    con.close()


def intelligence_tick():
    """One cycle of the intelligence loop."""
    log("CYCLE", "intelligence_tick_start")
    
    pending = get_pending_leads()
    if not pending:
        log("INFO", "no_pending_leads")
        return
    
    buyers = get_active_buyers()
    if not buyers:
        log("WARN", "no_active_buyers_with_payment")
        return
    
    log("INFO", "processing_batch", pending=len(pending), buyers=len(buyers))
    
    delivered = 0
    failed = 0
    
    for lead in pending:
        # 1. AI enrich
        lead = enrich_lead_with_ai(lead)
        
        # 2. Match buyer
        buyer = match_buyer_intelligently(lead, buyers)
        if not buyer:
            log("WARN", "no_buyer_match", lead_id=lead["id"])
            failed += 1
            continue
        
        # 3. Waterfall delivery
        success = deliver_lead(lead, buyer)
        
        if success:
            update_lead_status(lead["id"], "delivered", f"delivered_to_{buyer['prospect_id']}")
            delivered += 1
        else:
            update_lead_status(lead["id"], "pending", f"delivery_failed_{buyer['prospect_id']}")
            failed += 1
    
    log("CYCLE", "intelligence_tick_done", delivered=delivered, failed=failed, pending=len(pending))


def main():
    log("INFO", "intelligence_loop_starting", tick_interval=TICK_INTERVAL, batch_size=BATCH_SIZE)
    
    if os.environ.get("INTELLIGENCE_DAEMON", "1") == "1":
        while True:
            try:
                intelligence_tick()
            except Exception as e:
                log("ERROR", "tick_exception", error=str(e))
            time.sleep(TICK_INTERVAL)
    else:
        intelligence_tick()


if __name__ == "__main__":
    main()