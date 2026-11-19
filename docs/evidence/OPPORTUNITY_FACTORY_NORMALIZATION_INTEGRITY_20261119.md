# Opportunity Factory — actual-score integrity and genuine-buyer evidence boundary
Generated: 2026-11-19T11:48:52.298694+00:00
Production commit: `402a1951a680c4a853f05e30741aa0f10acaf511`

## Actual work delivered
- Existing Opportunity Factory intake now calculates score-bearing candidate counts from **parsed normalized values**, instead of trusting a claimed upstream count.
- Existing batch output reports per-blocker evidence gaps and distinct buyer-intent/demand value availability. Existing intake CLI displays this breakdown.
- No new timer, platform, provider, permission, sales automations or database write.
- Real production checkout: **59 focused tests PASS**; existing intake CLI invoked; output persisted and read back successfully.

## Evidence readback
- `runtime/opportunity_factory/intake_latest.json`: generated `2026-11-19T11:46:07.225502+00:00`
- `runtime/opportunity_factory/normalized_signals_latest.json`: generated `2026-11-19T11:45:20.805126+00:00`
- `runtime/market_sweeps/revenue_gps_latest.json`: generated `2026-11-19T11:31:33.153517+00:00`
- `runtime/opportunity_radar/latest.json`: generated `2026-11-19T11:44:54.169722+00:00`
- `runtime/astra/executive_latest.json`: generated `2026-11-19T11:48:42.654806+00:00`
- `runtime/conversations_replies_control/reply_linkage_plan_latest.json`: generated `2026-11-19T11:48:43.639356+00:00`
- Market GPS contains **100 markets**. **20 of 28** radar candidates have matching (niche, metro) Market GPS rows.
- Market GPS commercial demand market count: **0**; its restricted reply-lineage reader observed **0** canonical reply rows in the restricted lookback window. This is a source-scope observation, not proof no business replies exist elsewhere.
- Factory candidates: **28**, factory-ready **0**, actual populated normalized-score candidates **0**, parsed buyer-intent AND demand candidates **0**.
- Blocker counts: `{"build_complexity_normalized_score_required": 28, "buyer_intent_normalized_score_required": 28, "data_advantage_normalized_score_required": 28, "demand_normalized_score_required": 28, "distribution_path_required": 28, "distribution_strength_normalized_score_required": 28, "fulfilment_readiness_normalized_score_required": 28, "independent_evidence_required": 8, "margin_potential_normalized_score_required": 28, "offer_key_required": 28, "urgency_normalized_score_required": 28}`.
- Router stages unchanged: 8 DISCOVER; 20 QUALIFY.
- ASTRA verified derived VALIDATE/EXPERIMENT candidates: **0**; ranked existing owner workstreams from that evidence: **0**.
- Existing conversation reply lineage plan remains `SCHEMA_PATH_FOUND_DATA_PROOF_REQUIRED` with **0** joined rows proven. Older genuine inbound correspondence and sent outreach are not automatically current, tenant-bound factory buyer evidence.

## Exact outstanding gate
Existing founder-led commercial acquisition / Smart CRM and Market Intelligence owners must independently bind an **authentic, consented buyer or purchase-intent event** to a canonical company/tenant, appropriate market niche + metro, verified provider thread evidence, genuine offer/terms and an approved distribution path. Only after those facts pass the existing evidence normalizer and independent lifecycle history may a candidate be ranked in ASTRA. Do not turn public research counts, title-matched tenders, outbound sends or internal QA into intent/revenue.
No candidate promotion, customer, revenue, payment or checklist closure was claimed.
