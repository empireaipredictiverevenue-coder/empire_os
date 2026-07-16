#!/bin/bash
# Empire OS - one-shot backup.
# Usage: bash scripts/backup_now.sh [label]
# Outputs: /root/empire_os_backups/<label>/ + sha256sums.

set -e
LABEL="${1:-$(date -u +%Y-%m-%d_%H%M%S)}"
DEST="/root/empire_os_backups/${LABEL}"
mkdir -p "$DEST"

echo "[backup] -> $DEST"

# 1. SQLite (use .backup for ACID consistency)
DEST_DB="${DEST}/empire_os.db"
sqlite3 /root/empire_os/empire_os.db ".backup '$DEST_DB'"
echo "[backup] sqlite ok"

# 2. Feedback (chmod 777 mount, 24+ jsonl)
tar czf "${DEST}/feedback.tar.gz" -C /root feedback 2>/dev/null || true
echo "[backup] feedback tar ok"

# 3. Agent code + SOULs
tar czf "${DEST}/agents.tar.gz" -C /root/empire_os/empire_os agents 2>/dev/null
echo "[backup] agents tar ok"

# 4. Plan + scripts
cp /root/Empire_OS_Billion_Scale_Plan.md "$DEST/" 2>/dev/null || true
cp /root/empire_os/scripts/*.sh "$DEST/" 2>/dev/null || true

# 5. Skeel
cd "$DEST"
sha256sum empire_os.db feedback.tar.gz agents.tar.gz 2>/dev/null > SHA256SUMS || true
echo "[backup] sha256 ok"

# 6. size
du -sh "$DEST" | head -1
ls -la "$DEST" | head -10

echo "[backup] COMPLETE -> $DEST"
