# EmpireOS — Remote Commander duplicate-agent connection recovery

**Evidence date:** 13 October 2026, ~19:15 UTC. **Status: DIAGNOSED / RETIREMENT NOT APPROVED / NO SERVICE ACTION PERFORMED.**

## Production truth
- ChatGPT's Remote Desktop Commander sometimes reports EmpireOS **Online** yet subsequent commands fail with WebSocket/transport errors. Independent `ping` can succeed a few moments later. Online presence alone is not proof of usable command transport.
- `empire-desktop-commander.service`: systemd **enabled + active**, started 12 October 22:32 UTC, `Restart=always`, global npm distribution under `~/.nvm/versions/node/v22.23.2/lib/node_modules/@wonderwhy-er/desktop-commander`. Its process and helper were in `/system.slice/empire-desktop-commander.service`.
- A **second, unmanaged** `desktop-commander remote` process, launched 21 September 22:26 UTC from a cached `~/.npm/_npx/...` copy, remains parented to init in a historical user session (`/user.slice/user-1000.slice/session-805.scope`). Both copies maintained established TCP/443 connections at inspection, consistent with duplicate remote-agent registration.
- The managed unit's journal, from 13 October 17:00 UTC until inspection, counted **69 channel errors** and **69 online announcements**; errors included `socket closed: 1006` and `channel error: transport failure`. This establishes a real connection problem but **does not prove the duplicate process is its sole cause** (upstream network and provider failures remain possible).
- The unmanaged agent owns **long-lived child sessions**, including search/pipeline shells lasting 1–4 days and an interactive `pi` process lasting around 12 days. Their owner, state and effect on ASTRA's ongoing jobs have not been independently cleared. Blind `pkill`, `killall node`, `systemctl restart` or global task cleanup risks losing work.
- Separate `empire-ops-mcp.service` and `empire-remote-commander-tunnel.service` were active with healthy process status. No reason was found to rebuild those services, Cloudflare tunnels, ports or MCP authority.

## Lowest-risk next action — founder approval and session review required
1. Preserve a read-only inventory of both Commander process trees, start timestamps, systemd cgroups and active descendants. **Select processes by exact command + cgroup**, not historical PIDs (which will change).
2. Assign ownership of every long-lived child of the old `npx` agent. Save or complete interactive `pi` sessions and any real data-producing commands. Never assume a long-running terminal child is harmless just because it is old.
3. With explicit founder approval for the connection cutover, **gracefully retire ONLY the verified unmanaged `~/.npm/_npx` Remote Commander instance** once its child-session preservation check passes. Do not stop the managed systemd service, ops MCP, privileged helper or Cloudflare tunnel. Do not use a process-name-wide kill.
4. Independently prove exactly one Remote Commander agent registration remains, device ping + a read-only command both work, and the service journal's transport error rate improves in a **fresh** verification window. If errors persist, investigate upstream transport rather than repeating stop/start loops.
5. If rollback is necessary, assess managed-service status and previous configuration before any further action. Restarts/changes require their own explicit production approval. Preserve the audit of what was stopped.

## What this evidence does NOT authorise
- No termination, restart, disable, systemd rewrite, tunnel/DNS update, port change, credential readout, privilege escalation, bulk process cleanup or creation of another remote-agent supervisor/timer.
- No changes to EmpireDB, buyer/SEO work, payment/on-chain operations, email, launch traffic, or other ASTRA worktrees.
- This is an operator handoff, not a claim that Commander's WebSocket transport is now repaired.

**Command policy:** keep using the existing systemd-managed Desktop Commander through the authorised connector for strictly bounded actions; distinguish a successful `ping` from actual command success. Do not spawn a third `desktop-commander remote` as an attempted repair.

## Verified cutover outcome — 13 October 2026, 19:50–19:53 UTC

**The previously documented retirement hold has been resolved by explicit founder approval and a controlled operator cutover. This outcome supersedes the pre-cutover status above.**

- Owner-approved closure: exact old, read-only inspection sessions (historical PIDs 1310964, 2380185, 3282372) were individually terminated after reviewing available output. The separate idle `pi` smoke session (3948256) was terminated only after confirming the working directory and its `getlead_blitz_v1` Git branch `candidate/getlead-blitz-waterfall-convergence-v2` at commit `e18d5d88` had zero tracked modifications. No application migration, outbound, payments or product releases were running under those old session commands.
- Private, mode-`0600` preserved session audit: `/home/ubuntu/empire_agents/commander_cutover_20261013/legacy_terminal_session_audit.json`. This is a metadata/readback record, not a replayable full `pi` conversation transcript.
- The unmanaged September `npx` launcher (historical PID 610282) was retired by exact PID. The founder separately verified and gracefully signalled the legacy worker (historical PID 610308) only if its command line matched the known `~/.npm/_npx/4b4c857f6efdfb61/...` installation.
- The founder used `systemctl try-restart empire-desktop-commander.service`, returning `active`. New **managed** main PID 1206369, worker PID 1206429, starting 2026-10-13 19:50:48 UTC. Independent remote `ping` and `start_process` succeeded.
- Independent `/proc` checks show both old launcher/worker PIDs and all four legacy terminal PIDs absent. Exactly two Desktop Commander Node processes remain (one managed main, one managed child), both running the `~/.nvm/.../lib/node_modules/@wonderwhy-er/desktop-commander/dist/index.js` distribution. No `npx` remote agent remains.
- After the managed restart, **19 remote tool calls succeeded in being received with zero independently matched `❌ Channel error:` records** in the fresh managed-service journal window. A naive grep of raw journal contained false positives because tool-call arguments echoed the words `Channel error:`; strict prefix matching corrected the count. Short-window verification is not a lifetime uptime SLA.
- `empire-ops-mcp.service`, `empire-remote-commander-tunnel.service`, `empire-search-intelligence-api.service`, `empire-buyer-acquisition-scout.timer` and `empire-revenue-completion-supervisor.timer` remained active on the independent readback. The Search Console **true** status was confirmed via the same existing API. Nothing was changed in Cloudflare, DNS, database, site, checkout, search credentials, email or user traffic.
- Existing main repository tracked work and isolated ASTRA worktrees were preserved. No new timer, agent or supervisor was added.

**Outcome:** `CUTOVER_COMPLETE_INITIAL_REMOTE_VERIFICATION_PASS`. Keep the existing systemd-managed Remote Commander as the sole agent. If a future connector transport fault recurs, review the fresh service log and ping/command evidence before a narrowly approved fix. Do not reinstall or spawn another remote instance.
