#!/bin/bash
# serp_lane_feeder — weekly SERP intent sweep for every active
# serp_lane_feeder subscription. Fresh Omega-scored leads into crm_leads.
set -u
DB=/root/empire_os/empire_os.db
SUBS=$(sqlite3 "$DB" "SELECT json_extract(pair.value,'\$.niche'), json_extract(pair.value,'\$.metro') FROM si_subscription s, json_each('{}') pair WHERE s.plan='sku_serp_lane_feeder' AND s.status='active'" 2>/dev/null)
# niches/metros stored on sub row niche column (pipe format niche|metro)
SUBS=$(sqlite3 "$DB" "SELECT niche FROM si_subscription WHERE plan='sku_serp_lane_feeder' AND status='active' AND niche LIKE '%|%'")
if [ -z "$SUBS" ]; then
  echo "[serp_feeder] no active feeder subs"
  exit 0
fi
echo "$SUBS" | while IFS='|' read -r niche metro; do
  [ -z "$niche" ] && continue
  echo "[serp_feeder] sweeping $niche / $metro"
  curl -s -m 120 -X POST http://127.0.0.1:8081/v1/serp/sweep \
    -H 'Content-Type: application/json' \
    -d "{\"niche\":\"$niche\",\"metro\":\"$metro\",\"limit\":10,\"score\":true}"
  echo
done
echo "[serp_feeder] done"
