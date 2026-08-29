#!/usr/bin/env python3
"""empire_scheduler.py — SINGLE orchestrator. One process, serialized writers.

Replaces the 4 scattered crons. Phases run in order, one at a time:
  harvest  -> market_sweep --all (keyless OSM, 42 verticals x 11 metros)
  enrich   -> free empire_enricher waterfall (email/phone into crm_leads)
  bridge   -> valid crm_leads emails -> si_buyer_outreach (dedup) + junk-flag
  outreach -> Brevo send to valid pool

crm_leads = source of truth. si_buyer_outreach = derived.
"""
import sys, time
sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")  # daily_email_outreach lives here
import lead_harvest, daily_email_outreach

if __name__ == "__main__":
    t0 = time.time()
    print("[scheduler] === harvest + enrich + bridge ===", flush=True)
    lead_harvest.main()
    print(f"[scheduler] === outreach send ({int(time.time()-t0)}s) ===", flush=True)
    daily_email_outreach.main()
    print(f"[scheduler] DONE total {int(time.time()-t0)}s", flush=True)
