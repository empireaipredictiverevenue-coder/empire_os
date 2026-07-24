#!/usr/bin/env bash
# Empire OS v3 — Daily Crawler Stats
# Reads /root/empire_os/empire_os.db from inside the empire-hub container
# and prints a daily summary: lead volume, tier/strategy breakdown,
# expected revenue, top 5 latest leads.
#
# Runs via systemd timer at 09:00 UTC.
# Logs to /var/log/empire-crawler-stats.log + journal (tag: empire-crawler-stats).

set -euo pipefail

DB_PATH="/root/empire_os/empire_os.db"
CONTAINER="empire-hub"
HUB_URL="http://10.118.155.218:8081"
LOG_FILE="/var/log/empire-crawler-stats.log"
TODAY="$(date -u +%F)"

mkdir -p "$(dirname "$LOG_FILE")"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

# ── 1. Sanity: container up? DB exists? ────────────────────────────────
if ! incus list --format csv | grep -q "^${CONTAINER},"; then
  log "FATAL: container ${CONTAINER} not running"
  exit 1
fi

if ! incus exec "${CONTAINER}" -- test -f "${DB_PATH}"; then
  log "FATAL: ${DB_PATH} not found inside ${CONTAINER}"
  exit 1
fi

# ── 2. Run python3 inside container so we don't need sqlite3 binary ────
STATS="$(incus exec "${CONTAINER}" -- python3 - "$DB_PATH" "$TODAY" <<'PYEOF'
import sys
import sqlite3

db_path, today = sys.argv[1], sys.argv[2]

# ── Tier mapping: DB stores omega_tier in legacy values plus new S/A/B/C/D
TIER_MAP = {
    "S": "S", "A": "A", "B": "B", "C": "C", "D": "D",
    "tier_a": "A", "tier_b": "B",
    "silver": "B", "gold": "A",
    "": "D",
    None: "D",
}

# ── Strategy mapping: icp_name → one of {nurture, buyer_marketplace, ignore}
STRATEGY_MAP_KEYWORDS = {
    "buyer_marketplace": ["ready to buy", "high-value homeowner", "buyer", "immediate"],
    "nurture": ["expansion", "growing", "nurture"],
}


def normalize_tier(raw):
    return TIER_MAP.get(raw, "D")


def classify_strategy(icp_name, lead_score, icp_fit_score):
    name = (icp_name or "").lower()
    if any(k in name for k in STRATEGY_MAP_KEYWORDS["buyer_marketplace"]):
        return "buyer_marketplace"
    if any(k in name for k in STRATEGY_MAP_KEYWORDS["nurture"]):
        return "nurture"
    if (lead_score or 0) >= 70 or (icp_fit_score or 0) >= 70:
        return "buyer_marketplace"
    if (lead_score or 0) >= 40 or (icp_fit_score or 0) >= 40:
        return "nurture"
    return "ignore"


def fetch_table_leads(cur, table, date_col):
    """Return list of dicts for leads posted today from a given table."""
    rows = cur.execute(
        f"SELECT id, omega_tier, icp_name, lead_score, icp_fit_score, "
        f"       metro, niche, source FROM {table} WHERE date({date_col})=?",
        (today,),
    ).fetchall()
    return rows


def fetch_top5(cur, table, date_col, cols_sql):
    """Return top 5 latest leads from a given table for today."""
    return cur.execute(
        f"SELECT {cols_sql} FROM {table} WHERE date({date_col})=? "
        f"ORDER BY id DESC LIMIT 5",
        (today,),
    ).fetchall()


conn = sqlite3.connect(db_path)
cur = conn.cursor()

# ── Discover which tables exist & have data ────────────────────────────
TABLE_DATE_COL = {
    "crm_leads": "created_at",
    "lane_leads": "created_at",
}

# 1. Leads posted today (combined across sources)
total_today = 0
tier_counts = {"S": 0, "A": 0, "B": 0, "C": 0, "D": 0}
strat_counts = {"nurture": 0, "buyer_marketplace": 0, "ignore": 0}
expected_rev = 0.0
by_source = {}

all_today_rows = []
top5_pool = []

for table, date_col in TABLE_DATE_COL.items():
    try:
        # Check table exists
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
    except Exception:
        continue

    # count + tier/strategy
    if table == "crm_leads":
        rows = fetch_table_leads(cur, table, date_col)
        for (lid, ot, inm, ls, ifs, metro, niche, src) in rows:
            total_today += 1
            tier_counts[normalize_tier(ot)] += 1
            strat_counts[classify_strategy(inm, ls, ifs)] += 1
            expected_rev += (ls or 0) * 1.0 + (ifs or 0) * 0.5
            by_source[src or "unknown"] = by_source.get(src or "unknown", 0) + 1
        # top5 from crm_leads
        top5_rows = cur.execute(
            "SELECT id, source, business_name, metro, omega_tier, icp_tier, "
            "       icp_name, lead_score, created_at "
            "FROM crm_leads WHERE date(created_at)=? ORDER BY id DESC LIMIT 5",
            (today,),
        ).fetchall()
        top5_pool.extend(top5_rows)

    elif table == "lane_leads":
        rows = cur.execute(
            "SELECT id, omega_tier, icp_tier, icp_fit_score, metro, niche, "
            "       lead_score, omega_score "
            "FROM lane_leads WHERE date(created_at)=?",
            (today,),
        ).fetchall()
        for (lid, ot, icp_tier, ifs, metro, niche, ls, omega_score) in rows:
            total_today += 1
            tier_counts[normalize_tier(ot)] += 1
            # lane_leads has no icp_name — derive strategy from icp_tier + scores
            strat_counts[classify_strategy(icp_tier, ls or omega_score, ifs)] += 1
            expected_rev += (ls or omega_score or 0) * 1.0 + (ifs or 0) * 0.5
            by_source[niche or "unknown"] = by_source.get(niche or "unknown", 0) + 1
        # top5 from lane_leads
        top5_rows = cur.execute(
            "SELECT id, niche, metro, omega_tier, icp_tier, icp_fit_score, "
            "       icp_name, omega_score, created_at "
            "FROM lane_leads WHERE date(created_at)=? ORDER BY id DESC LIMIT 5",
            (today,),
        ).fetchall()
        # normalise to crm_leads-shaped tuples for unified top5
        top5_rows = [
            (r[0], r[1] or "lane_leads", f"#{r[0]}", r[2], r[3], r[4],
             r[6], int(r[7] or 0), r[8])
            for r in top5_rows
        ]
        top5_pool.extend(top5_rows)

# Combine top5 from both tables, take overall 5 latest
top5_pool.sort(key=lambda r: r[0] or 0, reverse=True)
top5 = top5_pool[:5]

# ── emit markdown-ish report ──────────────────────────────────────────
out = []
out.append(f"# Empire OS Crawler Daily Stats — {today} (UTC)")
out.append("")
out.append(f"Leads posted today: **{total_today}**")
if by_source:
    out.append("")
    out.append("## By source / niche")
    for src, n in sorted(by_source.items(), key=lambda x: -x[1])[:10]:
        out.append(f"  {src}: {n}")
out.append("")
out.append("## Tier breakdown (S/A/B/C/D)")
for t in ["S", "A", "B", "C", "D"]:
    out.append(f"  {t}: {tier_counts[t]}")
out.append("")
out.append("## Strategy breakdown")
for s in ["nurture", "buyer_marketplace", "ignore"]:
    out.append(f"  {s}: {strat_counts[s]}")
out.append("")
out.append(f"## Expected revenue today: ${expected_rev:,.2f}")
out.append("")
out.append("## Top 5 latest leads")
out.append("| id | source | business | metro | omega_tier | icp_tier | icp_name | score | created_at |")
out.append("|---:|---|---|---|---|---|---|---:|---|")
for r in top5:
    rid, src, biz, metro, ot, it, inm, score, ts = r
    out.append(
        f"| {rid} | {src} | {(biz or '')[:40]} | {metro or ''} | "
        f"{ot or ''} | {it or ''} | {(inm or '')[:30]} | {score or 0} | {ts} |"
    )

print("\n".join(out))
PYEOF
)"

# ── 3. Write to log + emit to stdout/journal ─────────────────────────
{
  log "===== crawler daily stats ====="
  printf '%s\n' "${STATS}"
  log "===== end report ====="
} | tee -a "$LOG_FILE"

# Also POST to hub health endpoint if available (best effort, non-blocking)
incus exec "${CONTAINER}" -- bash -c "
  curl -fsS -X POST -H 'Content-Type: application/json' --max-time 5 \
    -d '$(printf '%s' "${STATS}" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")' \
    '${HUB_URL}/v1/health/ingest' >/dev/null 2>&1
" || true

exit 0
