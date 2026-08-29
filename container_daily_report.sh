#!/bin/bash
# Empire OS v3 — Daily Report (Bash + sqlite3 CLI)
# Runs entirely in container using sqlite3 command line

set -e

DB="/root/empire_os/empire_os.db"
DATE=$(date -u +"%Y-%m-%d")
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Helper to run scalar query
scalar() {
    sqlite3 "$DB" "$1" 2>/dev/null
}

# Collect all data
TOTAL_LEADS=$(scalar "SELECT COUNT(*) FROM lane_leads")
LAST_24H=$(scalar "SELECT COUNT(*) FROM lane_leads WHERE created_at > datetime('now','-1 day') LIMIT 1000")
AVG_FIT=$(scalar "SELECT ROUND(AVG(MIN(100, MAX(0, icp_fit_score))), 1) FROM lane_leads WHERE icp_fit_score IS NOT NULL LIMIT 5000")
AVG_FIT=${AVG_FIT:-0}

BY_TIER_JSON=$(sqlite3 -json "$DB" "SELECT omega_tier, COUNT(*) as cnt FROM lane_leads GROUP BY omega_tier LIMIT 20" 2>/dev/null)

A2A_TOTAL=$(scalar "SELECT COUNT(*) FROM buyer_leads LIMIT 1000")
A2A_DELIVERED=$(scalar "SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status='http_200' LIMIT 1000")
A2A_LOCKED=$(scalar "SELECT ROUND(SUM(payout_usd), 2) FROM buyer_leads WHERE endpoint_status='http_200' LIMIT 1000")
A2A_LOCKED=${A2A_LOCKED:-0}

BUYERS_TOTAL=$(scalar "SELECT COUNT(*) FROM si_buyer_outreach LIMIT 1000")
BUYERS_PRICED=$(scalar "SELECT COUNT(*) FROM si_buyer_outreach WHERE payout_per_lead > 0 LIMIT 1000")
BUYERS_ENDPOINT=$(scalar "SELECT COUNT(*) FROM si_buyer_outreach WHERE endpoint_url != '' AND endpoint_url IS NOT NULL LIMIT 1000")

CHARGES_TOTAL=$(scalar "SELECT COUNT(*) FROM si_charges LIMIT 1000")
CHARGES_OPEN=$(scalar "SELECT COUNT(*) FROM si_charges WHERE status='open' LIMIT 1000")
CHARGES_PAID=$(scalar "SELECT COUNT(*) FROM si_charges WHERE status='paid' LIMIT 1000")
CHARGES_VAULT=$(scalar "SELECT ROUND(COALESCE(SUM(amount_cents), 0) / 100.0, 4) FROM si_charges WHERE status='paid' LIMIT 1000")
CHARGES_VAULT=${CHARGES_VAULT:-0}

SETTLEMENTS=$(scalar "SELECT COUNT(*) FROM si_settlements LIMIT 1000")

INVOICES_PENDING=$(scalar "SELECT COUNT(*) FROM si_invoice WHERE status='pending' LIMIT 1000")
INVOICES_PAID_TODAY=$(scalar "SELECT COUNT(*) FROM si_invoice WHERE status='paid' AND DATE(paid_at)=DATE('now') LIMIT 1000")
INVOICES_PAID_TOTAL=$(scalar "SELECT COUNT(*) FROM si_invoice WHERE status='paid' LIMIT 1000")

ACTIVE_SUBS=$(scalar "SELECT COUNT(*) FROM si_subscription WHERE status = 'active' AND price_cents > 0")

MRR_JSON=$(sqlite3 -json "$DB" "
    SELECT plan, billing_cycle, price_cents, COUNT(*) as subs
    FROM si_subscription
    WHERE status = 'active' AND price_cents > 0
    GROUP BY plan, billing_cycle, price_cents
" 2>/dev/null)

# Build JSON manually using cat and heredoc
cat <<EOF
{
  "ts": "$TS",
  "date": "$DATE",
  "revenue_snapshot": {
    "leads": {
      "total": $TOTAL_LEADS,
      "last_24h": $LAST_24H,
      "avg_fit_score": ${AVG_FIT:-0},
      "by_tier": $BY_TIER_JSON
    },
    "a2a": {
      "total": $A2A_TOTAL,
      "delivered_http_200": $A2A_DELIVERED,
      "locked_usd": $A2A_LOCKED
    },
    "buyers": {
      "total": $BUYERS_TOTAL,
      "priced": $BUYERS_PRICED,
      "with_endpoint": $BUYERS_ENDPOINT
    },
    "charges": {
      "total": $CHARGES_TOTAL,
      "open": $CHARGES_OPEN,
      "paid": $CHARGES_PAID,
      "vault_usdc": $CHARGES_VAULT
    },
    "settlements": {
      "rows": $SETTLEMENTS
    },
    "invoices": {
      "pending": $INVOICES_PENDING,
      "paid_today": $INVOICES_PAID_TODAY,
      "paid_total": $INVOICES_PAID_TOTAL
    },
    "mrr": {
      "active_subs": $ACTIVE_SUBS,
      "by_plan": $MRR_JSON
    }
  }
}
EOF