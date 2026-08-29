#!/usr/bin/env python3
"""
Email-only lead delivery fallback — bypasses webhook requirement.
Uses mail_sender's Brevo/Resend/SMTP to deliver leads via email.
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
from empire_os.mail_sender import _send

DB = "/root/empire_os/empire_os.db"

def deliver_lead_via_email(lead: dict, buyer: dict) -> bool:
    """Deliver lead via email when no webhook available."""
    prospect_id = buyer.get("prospect_id") or buyer.get("id")
    email = buyer.get("email") or buyer.get("contact_email")
    
    if not email:
        return False
    
    # Build lead email
    subject = f"New {lead.get('niche', 'lead')} lead for {lead.get('metro', 'your area')}"
    
    body = f"""
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
    
    try:
        result = _send(email, subject, body)
        success = result.get("ok", False)
        
        # Record delivery
        con = sqlite3.connect("/root/empire_os/empire_os.db")
        cur = con.cursor()
        cur.execute("""
            INSERT INTO buyer_leads 
            (buyer_id, lane_lead_id, prospect_id, niche, metro, omega_tier, 
             match_score, payout_usd, endpoint_status, endpoint_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prospect_id, lead.get("id"), prospect_id,
            lead.get("niche", ""), lead.get("metro", ""), lead.get("omega_tier", ""),
            0, buyer.get("payout_per_lead", 0),
            "email_sent" if success else "email_failed",
            json.dumps(result)
        ))
        
        # Update lane_leads status
        new_status = "delivered" if success else "pending"
        cur.execute(
            "UPDATE lane_leads SET status = ?, buyer_id = ? WHERE id = ?",
            (new_status, prospect_id, lead.get("id"))
        )
        con.commit()
        con.close()
        
        return success
    except Exception as e:
        return False

def get_buyers_with_email() -> list:
    """Get all active buyers with email addresses."""
    con = sqlite3.connect("/root/empire_os/empire_os.db")
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    
    # Get from si_buyer_outreach
    buyers = cur.execute("""
        SELECT prospect_id, business_name, email, niche, metro, 
               wallet, payout_per_lead, endpoint_url
        FROM si_buyer_outreach 
        WHERE active=1 AND email IS NOT NULL AND email != ''
    """).fetchall()
    con.close()
    return [dict(b) for b in buyers]

def run_email_delivery_cycle():
    """One cycle of email-based lead delivery."""
    from empire_os.intelligence_loop import get_pending_leads, match_buyer_intelligently
    
    pending = get_pending_leads(limit=50)
    if not pending:
        return {"delivered": 0, "failed": 0}
    
    buyers = get_buyers_with_email()
    if not buyers:
        return {"delivered": 0, "failed": 0, "error": "no buyers with email"}
    
    delivered = 0
    failed = 0
    
    for lead in pending:
        buyer = match_buyer_intelligently(lead, buyers)
        if not buyer:
            failed += 1
            continue
        
        # Try webhook first, fallback to email
        from empire_os.intelligence_loop import deliver_lead
        if deliver_lead(lead, buyer):
            delivered += 1
        else:
            # Fallback to email
            if deliver_lead_via_email(lead, buyer):
                delivered += 1
            else:
                failed += 1
    
    return {"delivered": delivered, "failed": failed}

if __name__ == "__main__":
    result = run_email_delivery_cycle()
    print(f"Email delivery cycle: {result}")
