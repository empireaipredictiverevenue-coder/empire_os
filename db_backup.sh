#!/bin/bash
# db_backup.sh — nightly SQLite backup of empire_os.db (anti-wipe insurance)
set -e
DB=/root/empire_os/empire_os.db
DST=/root/backups
mkdir -p "$DST"
TS=$(date +%Y%m%d-%H%M%S)
sqlite3 "$DB" ".backup '$DST/empire_os-$TS.db'"
# keep last 7
ls -1t "$DST"/empire_os-*.db 2>/dev/null | tail -n +8 | xargs -r rm -f
echo "backup done: $DST/empire_os-$TS.db"
