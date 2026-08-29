"""
Hourly Intelligence Retainer - $150/hr bespoke consulting.
Uses existing Cortex + Predictive + Neural Scout systems.
"""
import sqlite3, json, os, sys, time
from datetime import datetime, timezone

sys.path.insert(0, "/root/empire_os")
from empire_os.pay_link import build_pay_url, vault_address

DB = "/root/empire_os/empire_os.db"
RETAINER_DIR = "/root/empire_os/retainer"
os.makedirs(RETAINER_DIR, exist_ok=True)

PRODUCTS = [
    {"sku": "intel_hourly", "name": "Hourly Intelligence Retainer", "price": 150.0, "unit": "hour"},
]

def create_retainer_offer(client_email, client_name, hours=10):
    """Create a retainer offer for a client."""
    conn = sqlite3.connect(DB, timeout=10)
    c = conn.cursor()
    
    # Create offer record
    offer_id = f"retainer_{client_email}_{int(datetime.now().timestamp())}"
    total = hours * 150.0
    
    c.execute("""
        INSERT OR REPLACE INTO si_subscription 
        (tenant_id, plan, billing_cycle, seats, price_cents, status, payment_method, source, niche, per_lead_cents, started_at, current_period_end, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        offer_id,
        "intelligence_retainer",
        "hourly",
        1,
        int(total * 100),
        "awaiting_payment",
        "crypto_usdt_bsc",
        "hourly_retainer",
        "consulting",
        int(150 * 100),
        datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat(),  # current_period_end
        datetime.utcnow().isoformat()
    ))
    
    conn.commit()
    # Create a payable invoice (so the retainer is collectable, not phantom).
    inv_id = f"inv_ret_{int(time.time())}"
    amt_cents = int(total * 100)
    pay_url = build_pay_url(inv_id, amt_cents, memo=f"RET_{offer_id}")
    try:
        c.execute(
            "INSERT INTO si_invoice (invoice_id, tenant_id, subscription_id, "
            "amount_cents, currency, status, method, reference, description, "
            "created_at, pay_url, charged_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (inv_id, offer_id, offer_id, amt_cents, "USDT", "pending",
             "usdc_pending", offer_id,
             f"Hourly retainer {hours}h x $150",
             datetime.now(timezone.utc).isoformat(), pay_url,
             datetime.now(timezone.utc).isoformat()),
        )
        # queue collection email via si_outbox (mail-sender flushes)
        c.execute(
            "INSERT INTO si_outbox (to_email, subject, body, lane, tier, source, "
            "status, meta_json, buyer_tenant) VALUES (?,?,?,?,?,?,?,?,?)",
            (client_email, f"Empire OS retainer invoice — ${total:.2f} USDT (BSC)",
             f"Your hourly intelligence retainer ({hours}h x $150 = ${total:.2f}) "
             f"is ready.\nPay here: {pay_url}\nMemo: RET_{offer_id}\n"
             f"Invoice: {inv_id}", "revenue", "paid", "retainer_invoice",
             "pending", f'{{"invoice_id":"{inv_id}"}}', offer_id),
        )
    except Exception as e:
        print(f"  retainer invoice queue failed: {e}")
    conn.commit()
    conn.close()
    
    return {
        "offer_id": offer_id,
        "client": client_name,
        "email": client_email,
        "hours": hours,
        "rate": 150,
        "total": total,
        "invoice_id": inv_id,
        "pay_url": pay_url,
        "bsc_wallet": vault_address(),
        "usdt_contract": "0x55d398326f99059fF775485246999027B3197955"
    }

def generate_retainer_pdf(offer):
    """Generate retainer agreement text (PDF later)."""
    text = f"""EMPIRE AI — HOURLY INTELLIGENCE RETAINER AGREEMENT

Offer ID: {offer['offer_id']}
Client: {offer['client']} ({offer['email']})
Date: {datetime.utcnow().strftime('%Y-%m-%d')}

SCOPE
Empire AI provides bespoke intelligence consulting using Cortex Intelligence System:
- Niche heat scoring & competitor analysis (49,578 blueprints)
- Market share & visual DNA analysis
- Lead flow trends & pricing gap detection
- Custom research via Neural Scout + Deep Research agents

DELIVERABLES PER HOUR
1. Custom intelligence report (market size, competitors, opportunity gaps)
2. Cortex-generated niche analysis (heat score, demand/supply, ROI)
3. 30-min consultation call to review findings
4. Actionable recommendations for lead acquisition / market entry

TERMS
- Rate: $150/hour
- Hours purchased: {offer['hours']} hours = ${offer['total']:.2f}
- Payment: USDT on BSC (BEP-20)
- Wallet: {offer['bsc_wallet']}
- Contract: {offer['usdt_contract']}
- Minimum engagement: 5 hours
- Unused hours roll over 90 days
- Response time: 24 hours for requests, 48 hours for delivery

EXAMPLE REQUESTS
- "What's the roofing market opportunity in Dallas Q4 2026?"
- "Competitor analysis for HVAC companies in Houston metro"
- "Lead flow trends for water mitigation in Florida"
- "Pricing gaps in solar installation niche across Texas"
- "Visual DNA audit for my agency's client portfolio"

ACCEPTANCE
Send ${offer['total']:.2f} USDT to the wallet above with memo: {offer['offer_id']}
Email confirmation to founder@empire-ai.co.uk with transaction hash.
Work begins within 24 hours of payment confirmation.

--
Empire AI Intelligence
founder@empire-ai.co.uk
https://empire-ai.co.uk
"""
    return text

def send_retainer_offer(email, name, hours=10):
    """Send retainer offer via email (uses existing Brevo pipeline)."""
    offer = create_retainer_offer(email, name, hours)
    pdf_text = generate_retainer_pdf(offer)
    
    # Save offer
    with open(f"{RETAINER_DIR}/{offer['offer_id']}.txt", "w") as f:
        f.write(pdf_text)
    
    return offer, pdf_text

if __name__ == "__main__":
    # Demo: create offer for a test client
    offer, text = send_retainer_offer("client@example.com", "Test Client", 10)
    print(json.dumps(offer, indent=2))
    print("\n--- AGREEMENT ---")
    print(text[:500])