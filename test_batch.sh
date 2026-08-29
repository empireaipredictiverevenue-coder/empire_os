#!/bin/bash
# Empire OS v3 — Daily Report (Single incus exec with batch SQL)
# Runs all queries in ONE incus exec call to avoid timeout overhead

set -e

DB="/root/empire_os/empire_os.db"
DATE=$(date -u +"%Y-%m-%d")
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Single massive SQL batch that does everything
incus exec empire-hub -- bash -c "
sqlite3 /root/empire_os/empire_os.db '
SELECT 
    (SELECT COUNT(*) FROM lane_leads) as total_leads,
    (SELECT COUNT(*) FROM lane_leads WHERE created_at > datetime(\"now\",\"-1 day\") LIMIT 1000) as last_24h,
    (SELECT ROUND(AVG(MIN(100, MAX(0, icp_fit_score))), 1) FROM lane_leads WHERE icp_fit_score IS NOT NULL LIMIT 5000) as avg_fit,
    (SELECT COUNT(*) FROM buyer_leads LIMIT 1000) as a2a_total,
    (SELECT COUNT(*) FROM buyer_leads WHERE endpoint_status=\"http_200\" LIMIT 1000) as a2a_delivered,
    (SELECT ROUND(SUM(payout_usd), 2) FROM buyer_leads WHERE endpoint_status=\"http_200\" LIMIT 1000) as a2a_locked,
    (SELECT COUNT(*) FROM si_buyer_outreach LIMIT 1000) as buyers_total,
    (SELECT COUNT(*) FROM si_buyer_outreach WHERE payout_per_lead > 0 LIMIT 1000) as buyers_priced,
    (SELECT COUNT(*) FROM si_buyer_outreach WHERE endpoint_url != \"\" AND endpoint_url IS NOT NULL LIMIT 1000) as buyers_endpoint,
    (SELECT COUNT(*) FROM si_charges LIMIT 1000) as charges_total,
    (SELECT COUNT(*) FROM si_charges WHERE status=\"open\" LIMIT 1000) as charges_open,
    (SELECT COUNT(*) FROM si_charges WHERE status=\"paid\" LIMIT 1000) as charges_paid,
    (SELECT ROUND(COALESCE(SUM(amount_cents), 0) / 100.0, 4) FROM si_charges WHERE status=\"paid\" LIMIT 1000) as charges_vault,
    (SELECT COUNT(*) FROM si_settlements LIMIT 1000) as settlements,
    (SELECT COUNT(*) FROM si_invoice WHERE status=\"pending\" LIMIT 1000) as invoices_pending,
    (SELECT COUNT(*) FROM si_invoice WHERE status=\"paid\" AND DATE(paid_at)=DATE(\"now\") LIMIT 1000) as invoices_paid_today,
    (SELECT COUNT(*) FROM si_invoice WHERE status=\"paid\" LIMIT 1000) as invoices_paid_total,
    (SELECT COUNT(*) FROM si_subscription WHERE status = \"active\" AND price_cents > 0) as active_subs;
' 2>&1
"