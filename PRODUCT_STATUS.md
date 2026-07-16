# Empire OS v3 — PRODUCT STATUS (single source of truth)
# Maintained by Hermes. Last audit: 2026-07-16.
#
# STATUS KEY: DONE | PARTIAL | STUB | MISSING | BLOCKED
# DONE     = works end-to-end, verified
# PARTIAL  = core works, gaps remain
# STUB     = code exists but not wired/triggered/runnable
# MISSING  = spec exists, no real implementation
# BLOCKED  = cannot complete due to external dep (creds/provider/limits)

## SATELLITE / STORM PRODUCTS
- [DONE] daemon .env fix: all 13 empire-agent-*.service units now have `EnvironmentFile=/root/empire_os/.env`. Root cause was daemons never loaded .env → Supabase/Helius/Resend keys empty → dead agents. Verified: idle_asset + satellite_strike now see SUPABASE_SERVICE_KEY.
- [DONE] idle_asset (satellite/idle-asset+logistics product): active, Scope-correct (idle trucks / waste leakage / logistics waste via RSS). Writes to Supabase empire_tasks (task_type=idle_asset_review). Confirmed 3 rows @11:28 post-fix. Cycles clean: scanned=12/ tick.
- [DONE] satellite_strike (storm product): active, polls NWS alerts. NoneType crash (`"geometry":null`) FIXED (`or {}`). HUB default 10.118.155.218 (unreachable) → localhost:8081. Now cycles clean on real alerts (Tornado/Flash Flood/Red Flag Warnings).
- [PARTIAL] storm notify: alerts detected + POSTed to /v1/satellite/strike. Hub endpoint idempotent (200 already:true, no 500). 70 crm_leads created. `notified:0` = clean dedup, not failure.
- [PARTIAL] storm monetization bridge: deliver_storm_leads() being built — reads storm crm_leads -> matches roofing buyers -> bills 3x disaster premium via USDC invoice. PPL_DISASTER_MODE=on (.env). SUBAGENT RUNNING.

## LEAD GOLDMINE (56.6k recovered Jul 16, old Supabase owbeinlfcfdtwcwrttjy)
- Backup CSVs HOST /root/supabase_lead_backup/: prospects 41,638 / contractors 7,348 / enriched_leads 6,822 / b2b_leads 775 / buyers 14.
- Live: 29,029 prospects -> hub si_buyer_outreach. Idle: ~12.6k prospects + 14,945 (contractors+enriched+b2b). Total ~27.6k idle.
- REAL PPL rates (buyers table): Roofing $1.70/lead, Mass Tort $12, Consumer CPA $2.25. Blended ~$5. Disaster MULTIPLIER=3.0.
- 56.6k x $5 = ~$283k theoretical; ~$60-115k realistic.

## INFRA
- [DONE] daemon env: all 13 units load /root/empire_os/.env via EnvironmentFile.
- [DONE] Supabase live DB: old project owbeinlfcfdtwcwrttjy reused (44k leads). PostgREST layer sb.py built + proven.
- [DONE] Email key: Resend re_RgQAP... valid, domain empire-ai.co.uk verified.
- [BLOCKED] Full SQLite→Supabase migration: pooler host region unknown (IPv6 direct dead). 57 backend.execute call sites still SQLite.
- [BLOCKED] MiniMax M3 LLM: out of limits (few days). Agents needing LLM 503.

## LEAD GEN / OUTREACH
- [DONE] 44k leads recovered + backed up (/root/supabase_lead_backup/, 21MB).
- [DONE] 29,029 prospects migrated → si_buyer_outreach (hub outreach engine). Verified via /v1/outreach/prospects/pending.
- [DONE] lead_sniper guard-railed: rule-based (MD), review-only→Supabase, dedup+cap+KILL. Verified.
- [PARTIAL] email_agent: drafts→operator-approval. NO auto-send. Sends via Resend (proven 2228). Rate-limited (1010) from burst, recovers.
- [STUB] media_buyer: reads prospects, plans only. Does NOT execute ppc charges or write invoices. /v1/ppc/log_invoice exists, unused.
- [MISSING] ppc revenue tracking for the 44k leads (no agent writes si_ppc_invoices).

## STORM / SATELLITE (storm damage product)
- [PARTIAL] satellite_damage_agent: scans damage, finds owner_email, queues Storm Damage email to owner via si_outbox. NO-SIM compliant (skips no-email).
- [MISSING] PDF damage report to owner: spec was "scan warehouse storm damage → PDF sent to owner". NO PDF generation exists in flow. Plain text email + opt-in URL only.
- [STUB] Damage scan NOT on a loop: /v1/damage/scan + /scan-all exist but nothing triggers them. Dead (event-driven only).
- [DONE] satellite_strike (storm cell alerts): fixed null-geometry crash earlier. NOT on loop either.

## WASTE / IDLE-TRUCK / LOGISTICS (separate product — you approved build)
- [DONE] idle_asset_sniper_agent.py built: rule-based (no LLM), scans feeds + idle_asset_enriched (1,677 real assets), scores idle/waste/logistics signals, review-only→Supabase empire_tasks. VERIFIED (8 real assets found, scored 0.67).
- [DONE] Launched as daemon (empire-agent-idle_asset.service), active, reboot-surviving.
- [PARTIAL] idle_asset_scans table EMPTY (unused). Agent routes to empire_tasks review queue instead (proven path). Can populate idle_asset_scans later once schema known.
- [MISSING] Real satellite imagery (pixel ML) — not available; built data-feed version instead (works now).

## SUPABASE CONNECTIVITY (RESOLVED — PostgREST only)
- [DONE] PostgREST (sb.py) over IPv4 — WORKS. All agent writes use it.
- [BLOCKED-FINAL] psycopg (direct db.:5432 OR pooler :6543): 
  - db. host = IPv6 only (Vultr no IPv6 route) -> unreachable.
  - *.pooler.supabase.com does NOT resolve in DNS (tested eu-west-2, eu-west-1, eu-central-1, us-east-1, fake). Even supabase.com resolves; pooler subdomain doesn't exist for this project.
  - CONCLUSION: psycopg impossible for this project. PostgREST is the only DB path.
- [ARCHITECTURE] Hub keeps SQLite for internal CRM (si_buyer_outreach, si_outbox, si_ppc_invoices). Supabase (PostgREST) holds lead/review data. 44k prospects migrated into hub SQLite outreach table; agents use sb.py for review queues.

## REVENUE LOOP (ppc / invoices / USDC)
- [DONE] lead_deliverer: delivers leads to buyers (webhook+HMAC + email) AND invoices pay-per-lead to si_ppc_invoices (USDC = base_payout*fee_rate). VERIFIED live: POST /v1/ppc/log_invoice -> row in ledger ($12.00, status open).
- [DONE] Hub /v1/ppc/log_invoice FIXED: `int(head)` crash -> `str(head)` (was 500 on every invoice). Now 200.
- [DONE] lead_deliverer daemonized (empire-agent-lead_deliverer.service), active.
- [BLOCKED] Live USDC collection test: no vault funds to send (user confirmed). Code path complete: solana_listener watches vault, marks invoice paid on USDC receipt. Unverified on-chain until funded.
- [DONE] Live USDC collection VERIFIED: user sent 0.528861 USDC to vault egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM (Phantom→TokenPocket, no memo). Listener detected via ATA balance-delta, hub /v1/finance/replay matched si_ppc_invoices by amount (528861 micro), flipped invoice to PAID. Loop closed + repeated live.
- [DONE] Vault address corrected: was truncated 43-char (returned 0), now real 44-char egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM in hub .env + listener.
- [DONE] solana_listener rewritten: balance-delta detection (no getTransaction dependency, robust), sends micro-USDC to match invoice schema. Handles no-memo payments (TokenPocket/Trust Wallet).
- [DONE] Hub /v1/finance/replay: memo now optional, matches si_ppc_invoices by amount (±1 micro), uses paid_at (not nonexistent payment_ref). Hub 8081 now systemd unit empire-hub-8081.service (Restart=always).

## KNOWN GAPS / TODO
1. Trigger damage scan on a loop (warehouse storm damage → owner email).
2. Build PDF damage report → email to owner (was "supposed to be done").
3. Wire media_buyer ppc → Supabase invoices for 44k leads.
4. Build idle-truck/waste/logistics detector (data-feed) → idle_asset_scans → review.
5. Full Supabase migration (needs pooler host).
6. Verify Solana vault address + test USDC collection.
7. This file was MISSING — that's why nothing was tracked. Now it exists.

## STRUCTURAL FIX (2026-07-16) — the stub problem
- [DONE] Agent supervisor built: /root/empire_os/empire_os/supervisor_daemon.py
- [DONE] Registry: /root/empire_os/empire_os/agent_registry.json (21 agents classified, 11 daemons enabled)
- [DONE] 11 daemons launched as systemd units (empire-agent-*.service), Restart=always, survive reboot.
- [DONE] NO-SIM gate: sim agents (satellite_damage, synthetic_*) disabled unless ALLOW_SIM=1.
- [DONE] Fixed venv python path (was /usr/bin/python3 without requests → all crashed).
- TODO: extend registry to all 64 agents; fix email_agent 400 + solana_listener stability.
