#!/usr/bin/env bash
# Empire OS DB Sync — container -> host (safe)
# Pulls a SQLite backup from the container, verifies it, then atomically
# replaces the host's empire_os.db. Container is source of truth.
set -euo pipefail

CONTAINER_DB="/root/empire_os/empire_os.db"
HOST_DB="/root/empire_os/empire_os.db"
WAL="${HOST_DB}-wal"
SHM="${HOST_DB}-shm"
BACKUP_DIR="/root/empire_os/feedback/db_snapshots"
TMP="/tmp/empire_sync_$$"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
LOG="/root/feedback/db_sync.log"

mkdir -p "$BACKUP_DIR"
mkdir -p "$TMP"

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"
}

# 1. Pull SQLite backup to a temp dir (atomic file write, then move)
incus exec empire-hub -- /root/venv/bin/python3 << 'PYEOF' 2>>"$LOG"
import sqlite3
src = sqlite3.connect('/root/empire_os/empire_os.db')
dst = sqlite3.connect('/tmp/snap.db')
with dst:
    src.backup(dst)
src.close()
dst.close()
PYEOF
incus file pull empire-hub/tmp/snap.db "$TMP/snap.db" 2>>"$LOG"
incus exec empire-hub -- rm -f /tmp/snap.db

# 2. Verify integrity of the snapshot
if ! /root/venv/bin/python3 -c "
import sqlite3, sys
try:
    con = sqlite3.connect('$TMP/snap.db', timeout=30.0)
    n = con.execute('SELECT COUNT(*) FROM lane_leads').fetchone()[0]
    con.execute('PRAGMA integrity_check').fetchall()
    con.close()
    print(f'snap_ok:{n}')
except Exception as e:
    print(f'snap_err:{e}', file=sys.stderr)
    sys.exit(1)
" 2>>"$LOG"; then
    log "ERR snapshot integrity check failed; aborting"
    rm -rf "$TMP"
    exit 1
fi

SNAP_SIZE=$(stat -c %s "$TMP/snap.db")
log "snapshot OK: ${SNAP_SIZE} bytes"

# 3. Keep last 3 snapshots
ls -t "${BACKUP_DIR}"/snap_*.db 2>/dev/null | tail -n +4 | xargs -r rm -f

# 4. Atomically replace host DB
#    a) Move current host DB to backup (so a rollback is possible)
#    b) Move snapshot into place
#    c) Apply WAL mode
mv -f "$HOST_DB" "${BACKUP_DIR}/snap_${TIMESTAMP}_prev.db" 2>>"$LOG" || {
    log "ERR could not move host DB aside"
    rm -rf "$TMP"
    exit 1
}
mv -f "$TMP/snap.db" "$HOST_DB"
rm -rf "$TMP"
rm -f "$WAL" "$SHM"  # clear stale -wal/-shm from the old file

# 5. Apply WAL + busy_timeout on the freshly-placed DB
/root/venv/bin/python3 -c "
import sqlite3
c = sqlite3.connect('${HOST_DB}', timeout=30.0)
c.execute('PRAGMA journal_mode=WAL')
c.execute('PRAGMA busy_timeout=30000')
c.close()
" 2>>"$LOG"

log "sync complete: ${HOST_DB} (${SNAP_SIZE} bytes) <- container"
exit 0