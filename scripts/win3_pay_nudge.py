#!/usr/bin/env python3
"""
WIN 3: Pay Nudge — Email the 570 awaiting_payment subscriptions with invoice link
Run: python3 /root/empire_os/scripts/win3_pay_nudge.py --dry-run  (first run)
Run: python3 /root/empire_os/scripts/win3_pay_nudge.py             (live)
"""

import sys, os, json, sqlite3, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")

DB = "/root/empire_os/empire_os.db"
NUDGE_LOG = "/root/feedback/pay_nudge_log.jsonl"

PAY_NUDGE_TEMPLATE = """Subject: Your Empire OS invoice is still open — pay in USDC

Hi {business_name},

Your subscription to the {niche} lane in {metro} is still awaiting payment.

Invoice: {invoice_id}
Amount: ${amount_usd:.2f} USDC
Due: {created_at}

Pay now: {pay_url}

Or send USDC directly to our vault:
{economy_vault}

Once paid, your lead delivery begins immediately.

— Empire OS
"""

def get_awaiting_subscriptions(limit: int = 100, days_since_last_nudge: int = 7):
    """Get open USDC charges with open invoices that need payment nudges"""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_since_last_nudge)).isoformat()
    
    rows = conn.execute("""
        SELECT 
            c.charge_id,
            c.buyer_id,
            c.amount_cents,
            c.currency,
            c.status,
            c.processor_response,
            c.created_at as charge_created,
            i.invoice_id,
            i.amount_usdc,
            i.status as invoice_status,
            i.metadata,
            i.created_at as invoice_created
        FROM si_charges c
        JOIN si_ppc_invoices i ON i.charge_id = c.charge_id
        WHERE c.status = 'open'
        AND c.currency = 'USDC'
        AND i.status = 'open'
        AND c.created_at < ?
        ORDER BY c.created_at ASC
        LIMIT ?
    """, (cutoff, limit)).fetchall()
    
    conn.close()
    return [dict(r) for r in rows]

def get_vault_address():
    """Get USDC vault address from environment or .env file"""
    import os
    # First try environment variable
    vault = os.environ.get("SOLANA_VAULT_WALLET", "").strip()
    if vault:
        return vault
    
    # Try reading from .env
    env_path = Path("/root/empire_os/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("SOLANA_VAULT_WALLET="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    
    # Fallback from SETTLEMENT_RUNBOOK (truncated for security)
    return "egJ1t9NZkDs8FvMbfnQTqXzC4KNuhA..."

def get_pay_url(invoice_id: str) -> str:
    """Generate payment URL for invoice"""
    base = os.environ.get("EMPIRE_PUBLIC_URL", "https://empire-ai.co.uk")
    return f"{base}/pay/{invoice_id}"

def send_nudge_email(to_email: str, subject: str, body: str) -> dict:
    """Send email via hub's mail sender (uses EMAIL_BACKEND)"""
    import urllib.request, urllib.error
    
    hub_url = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
    url = f"{hub_url}/v1/outreach/webhook"
    
    payload = json.dumps({
        "source": "pay_nudge",
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "metadata": {"nudge_type": "pay_nudge"}
    }).encode()
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}", "detail": e.read().decode()[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--days-since-nudge", type=int, default=7)
    parser.add_argument("--send-limit", type=int, default=50, help="Max emails to send this run")
    args = parser.parse_args()
    
    print(f"=== WIN 3: PAY NUDGE ===")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"Limit: {args.limit} subscriptions, max {args.send_limit} emails")
    print(f"Days since last nudge: {args.days_since_nudge}")
    print()
    
    vault = get_vault_address()
    print(f"USDC Vault: {vault}")
    
    subs = get_awaiting_subscriptions(args.limit, args.days_since_nudge)
    print(f"Found {len(subs)} subscriptions awaiting payment with pending invoices")
    
    if not subs:
        print("No targets. Exiting.")
        return
    
    sent = 0
    skipped = 0
    errors = 0
    
    for i, sub in enumerate(subs, 1):
        if sent >= args.send_limit:
            print(f"  Reached send limit ({args.send_limit}). Stopping.")
            break
        
        # Extract data from charge/invoice structure
        charge_id = sub.get("charge_id")
        wallet = sub.get("wallet") or "there"
        amount_cents = sub.get("amount_cents") or 0
        amount_usd = amount_cents / 100.0
        invoice_id = sub.get("invoice_id")
        invoice_status = sub.get("invoice_status")
        solana_pay_url = sub.get("solana_pay_url")
        invoice_created = sub.get("invoice_created", "")
        
        # Try to extract business name from wallet or raw_response
        business_name = wallet.split("@")[0] if "@" in wallet else wallet
        if business_name == "there":
            import re
            # Try to parse raw_response for invoice_id
            raw = sub.get("raw_response", "")
            if isinstance(raw, str):
                try:
                    import json as _json
                    parsed = _json.loads(raw)
                    business_name = parsed.get("to", "there").split("@")[0]
                except:
                    pass
        
        niche = "crypto"  # default for USDC invoices
        metro = "online"  # default
        
        tenant_email = sub.get("tenant_email") or wallet
        sub_id = sub.get("subscription_id") or charge_id
        
        # Use solana_pay_url from invoice if available, otherwise construct
        pay_url = solana_pay_url or get_pay_url(invoice_id)
        
        subject = f"Your Empire OS invoice {invoice_id} — ${amount_usd:.2f} USDC"
        body = PAY_NUDGE_TEMPLATE.format(
            business_name=business_name,
            niche=niche,
            metro=metro,
            invoice_id=invoice_id,
            amount_usd=amount_usd,
            created_at=invoice_created[:10] if invoice_created else "",
            pay_url=pay_url,
            economy_vault=vault
        )
        
        print(f"  [{i}] {sub_id} → {tenant_email} | ${amount_usd:.2f} | {pay_url}")
        
        if args.dry_run:
            print(f"      DRY RUN — would send to {tenant_email}")
            continue
        
        # Send email
        result = send_nudge_email(tenant_email, subject, body)
        
        log_entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "pay_nudge",
            "subscription_id": sub_id,
            "tenant_email": tenant_email,
            "invoice_id": invoice_id,
            "amount_usd": amount_usd,
            "result": result,
            "dry_run": False
        }
        
        Path(NUDGE_LOG).parent.mkdir(parents=True, exist_ok=True)
        with open(NUDGE_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        if result.get("ok"):
            print(f"      ✅ SENT")
            sent += 1
        else:
            print(f"      ❌ FAILED: {result.get('error')}")
            errors += 1
        
        time.sleep(0.5)  # throttle
    
    print(f"\n=== PAY NUDGE COMPLETE ===")
    print(f"Sent: {sent}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")
    
    if args.dry_run:
        print("\n💡 Run without --dry-run to actually send emails")

if __name__ == "__main__":
    main()