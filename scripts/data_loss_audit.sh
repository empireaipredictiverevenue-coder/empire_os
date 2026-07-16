#!/bin/bash
# Empire OS - data-loss audit + backup policy
set -e
echo "=== Empire OS data-loss audit ==="
echo
echo "[1] state locations"
echo "  host:     /root/empire_os/empire_os.db (sqlite hub)"
echo "  container: /root/empire_os/empire_os.db (sqlite hub) -- via bind mount"
echo "  feedbacks: /root/feedback/ (24+ jsonl audit logs)"
echo "  plan:      /root/Empire_OS_Billion_Scale_Plan.md (v4)"
echo "  SOULs:     /root/empire_os/empire_os/agents/souls/*.md"
echo "  skills:    /root/.hermes/skills/empire-os-v3-snapshot/"
echo "  scripts:   /root/empire_os/scripts/ (agent_registry.py, write_env.py, ...)"
echo
echo "[2] data-loss risks we have today"
echo "  - host disk corrupted     -> sqlite hub lost (1 fatal risk)"
echo "  - container destroys DB   -> docker/criu snapshot saves us daily"
echo "  - .env overwritten        -> rebuildable from write_env.py prompts"
echo "  - SOULs deleted           -> recreate, no harm"
echo "  - feedback jsonl crashes  -> persistent (chmod 777 bind mount)"
echo "  - skills repo deleted     -> re-clone from anthropics/skills GitHub"
echo
echo "[3] WHERE THE REAL RISK IS"
echo "  NO DAILY BACKUP. If this Vultr instance dies tomorrow,"
echo "  we lose: 8K leads, 24 feedback logs, 30 SOULs, all 49"
echo "  agent config, billing tier changes, payment history."
echo
echo "[4] BACKUP PLAN (host-side)"
echo "  A. nightly snapshot to /root/empire_os_backups/YYYY-MM-DD/"
echo "     - tar.gz SQLite hub + feedback + soul + scripts"
echo "     - ship to S3 / R2 nightly"
echo "  B. incus snap empire-hub daily + zfs-send to backup store"
echo "  C. pg_dump equivalent -> sqlite .backup stdout -> compressed"
echo
echo "[5] how to verify access TODAY"
echo "  ls -la /root/empire_os/empire_os.db            (host DB)"
echo "  ls -la /root/empire_os/empire_os/agents/souls  (SOULs)"
echo "  ls -la /root/feedback/*.jsonl                  (logs)"
echo "  incus list -c ns -f csv | wc -l                  (fleet)"
echo "  curl http://10.118.155.218:8081/v1/health       (hub alive)"
