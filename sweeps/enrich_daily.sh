#!/bin/bash
# Daily enrichment + ICP rescore pipeline
# Runs inside empire-hub container via incus exec
set -e

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Enrichment pipeline start"

# Step 1: Batch enrich up to 50 leads with lowest enrichment scores
echo "--- Batch enrich ---"
ENRICH=$(curl -sS --noproxy '*' -X POST http://127.0.0.1:8081/v1/crm/leads/batch-enrich)
echo "$ENRICH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Enriched: {d.get(\"enriched\",\"?\")} leads, errors: {d.get(\"errors\",0)}')" 2>&1 || echo "$ENRICH"

# Step 2: Batch rescore all leads via ICP
echo "--- ICP Batch rescore ---"
SCORE=$(curl -sS --noproxy '*' -X POST http://127.0.0.1:8081/v1/crm/icp/batch)
echo "$SCORE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Scored: {d.get(\"updated\",\"?\")}')" 2>&1 || echo "$SCORE"

# Step 3: Report summary
echo "--- CRM summary ---"
python3 -c "
import sqlite3
conn = sqlite3.connect('/root/empire_os/empire_os.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT icp_tier, COUNT(*) as cnt FROM crm_leads GROUP BY icp_tier ORDER BY icp_tier').fetchall()
for r in rows: print(f'{r[\"icp_tier\"]}: {r[\"cnt\"]}')
print(f'Total scored: {sum(r[\"cnt\"] for r in rows)}')
" 2>/dev/null || echo "DB stats N/A"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Enrichment pipeline done"
