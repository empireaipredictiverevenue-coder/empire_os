"""
Retainer email sender - sends retainer offers via Brevo.
"""
import sqlite3, json, urllib.request, os, sys
sys.path.insert(0, "/root/empire_os/empire_os")

from hourly_retainer import send_retainer_offer

BREVO_KEY = open("/root/empire_secrets/brevo_api_key").read().strip()

def send_brevo(to_email, subject, body):
    payload = json.dumps({
        "sender": {"name": "Empire AI", "email": "empireaipredictiverevenue@gmail.com"},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }).encode()
    
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={"Content-Type": "application/json", "api-key": BREVO_KEY, "User-Agent": "curl/8.5.0"})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            return True, result.get("messageId", "")
    except Exception as e:
        detail = ""
        if hasattr(e, "read"):
            try: detail = e.read().decode()[:200]
            except: pass
        return False, detail or str(e)[:200]

def send_retainer_email(email, name, hours=10):
    """Send retainer offer email to a prospect."""
    offer, agreement = send_retainer_offer(email, name, hours)
    
    subject = f"Hourly Intelligence Retainer — ${hours*150:,.0f} for {hours} hours"
    body = f"""Hi {name},

Empire AI is offering a bespoke intelligence retainer for agencies and investors who need real-time market intelligence without building their own research team.

**Offer:** {hours} hours at $150/hr = ${hours*150:,.2f}
**Payment:** USDT on BSC (BEP-20)
**Wallet:** 0x1339b487046B0ad924a10c20b1791608EA8595a8

What you get per hour:
- Custom niche analysis (heat score, competitors, market share)
- Visual DNA audit (brand consistency, mobile optimization, visual strength)  
- Lead flow trends & pricing gap detection
- 30-min consultation call with findings
- Actionable recommendations for lead acquisition

Example requests we fulfill:
- "Roofing market opportunity in Dallas Q4 2026"
- "Competitor analysis for HVAC in Houston metro"
- "Lead flow trends for water mitigation in Florida"
- "Visual DNA audit for agency client portfolio"

Minimum 5 hours (${750}). Unused hours roll over 90 days.
Response time: 24hrs request, 48hrs delivery.

Reply to this email or send payment to the BSC wallet with memo: {offer["offer_id"]}

--
Empire AI Intelligence
"""
    
    ok, result = send_brevo(email, subject, body)
    return ok, result, offer

if __name__ == "__main__":
    import sys
    email = sys.argv[1] if len(sys.argv) > 1 else "test@example.com"
    name = sys.argv[2] if len(sys.argv) > 2 else "Test Client"
    hours = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    ok, result, offer = send_retainer_email(email, name, hours)
    print(f"Sent: {ok}, Result: {result}")
    print(f"Offer ID: {offer['offer_id']}")