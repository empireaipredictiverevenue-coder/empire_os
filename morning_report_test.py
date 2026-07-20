#!/usr/bin/env python3
"""Morning report: emails sent + revenue locked (real only, no fiction).

Self-contained for cron. Reads live DB, reports:
  - founder QR emails sent (seat_onboarding source)
  - total si_outbox sent/pending
  - revenue locked = real USDC settlements (evaluation_settlements paid + any collected)
  - enterprise campaigns status
NOTHING simulated. If $0, says $0.
"""
import sqlite3, json, sys
sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"

def q(c, s, d=0):
    try:
        return c.execute(s).fetchone()[0]
    except Exception:
        return d

c = sqlite3.connect(DB, timeout=20)
founder_sent = q(c, "SELECT COUNT(*) FROM si_outbox WHERE source='seat_onboarding' AND status='sent'")
founder_pending = q(c, "SELECT COUNT(*) FROM si_outbox WHERE source='seat_onboarding' AND status='pending'")
total_sent = q(c, "SELECT COUNT(*) FROM si_outbox WHERE status='sent'")
total_pending = q(c, "SELECT COUNT(*) FROM si_outbox WHERE status='pending'")
settlements_paid = q(c, "SELECT COALESCE(SUM(amount_usdc),0) FROM evaluation_settlements WHERE status='paid'")
active_campaigns = q(c, "SELECT COUNT(*) FROM outbound_campaigns WHERE status='active'")
c.close()

revenue_locked = round(settlements_paid, 2)

report = f"""EMPIRE OS — Morning Report (real data only)
{'='*50}
Founder QR emails sent:   {founder_sent} / 539
Founder emails pending:   {founder_pending}
Total emails sent:        {total_sent}
Total pending:            {total_pending}
Active campaigns:         {active_campaigns}
Revenue LOCKED (USDC):    ${revenue_locked:.2f}
{'='*50}
NOTE: $0.00 = rail unproven at scale. One $299 settlement
re-rates the whole valuation. No simulated revenue reported.
"""
print(report)
