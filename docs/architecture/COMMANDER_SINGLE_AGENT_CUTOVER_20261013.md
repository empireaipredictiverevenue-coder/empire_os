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
