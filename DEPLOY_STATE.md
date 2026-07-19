# Empire OS — Runtime State (2026-07-18 closure)

## Topology (truth)
- `empire-hub` incus container: 10.118.155.218. Holds the app at
  `/root/empire_os` (INSIDE the container — a SEPARATE copy from the host
  `/root/empire_os`; different inodes. Edits to host copy do NOT reach the
  running container. Always fix inside the container via `incus exec`.)
- Hub serves on **:8081** (systemd `empire-hub-8081.service`, Restart=always).
  NOT :8000, NOT :8080.
- Host reaches hub at `http://10.118.155.218:8081`.
- Caddy proxies empire-ai.co.uk / 302ai.net → localhost:8081 (correct).

## What runs
- 20 empire systemd units inside empire-hub (hub + 14 agents + ppc-router +
  mail-sender + billing-collector + sentry + solana-listener + lanes).
  All `Restart=always` → self-healing. NO separate supervisor needed.
- `empire-agent-supervisor.service` is **masked/disabled** (was a pm2
  respawn hydra — see below). Do not re-enable without removing pm2 calls.

## Killed landmines (do not reintroduce)
1. **pm2 god daemon** — inside container, self-respawning, hijacked :8000 and
   fought the systemd hub. FIXED: binary locked (chmod 000), `/root/.pm2`
   deleted, supervisor no longer calls pm2. Container pm2 = 0.
2. **:8000 split-brain** — every agent defaulted to `127.0.0.1:8000` (dead).
   FIXED: all .py repointed to :8081 in BOTH copies; HUB_URL env override
   on every systemd unit + host `.env`.
3. **/root/feedback permission lock** — dir was `drwx------ nobody`, crashed
   6 agents on log write. FIXED: chmod 777 (uid-map crossing).
4. **Supervisor pm2 dependency** — supervisor called `_run([pm2,"restart"])`
   every cycle, resurrecting the god daemon. FIXED: now systemctl-only.

## Leads (real, traced)
- crm_leads 7,449 = 6,476 `supabase_prospects` (recovered 56.6k backup) +
  973 `market_sweep`. lane_leads 2,453. si_buyer_outreach 728.
- Total ~10,630 across tables. NOT fabricated.

## Verification (post-fix)
- hub :8081 HTTP 200 (host + container)
- container pm2 = 0, :8000 listeners = 0
- 20/20 empire units active
- feedback writable

## If hub ever dies
`incus exec empire-hub -- systemctl restart empire-hub-8081.service`
Never start a second hub on :8000/:8080. Never use pm2 in the container.
