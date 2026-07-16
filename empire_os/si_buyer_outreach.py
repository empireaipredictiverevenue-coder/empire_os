"""
Empire OS v3 — Buyer Outreach schema
====================================

Table si_buyer_outreach — tracks every outreach interaction:

  - prospect_id (uniq)
  - business_name
  - email
  - metro
  - niche
  - phone
  - source (yelp/permits/court/reddit)
  - score
  - first_touch_at
  - last_touch_at
  - touch_count
  - reply_state (cold/contacted/replied/unsubscribed)
  - sample_lead_id (if sample lead delivered)
  - converted (set when buyer signed up)

Idempotent: inserts use OR REPLACE on prospect_id so re-running
the crawler never double-sends to the same contact.
"""