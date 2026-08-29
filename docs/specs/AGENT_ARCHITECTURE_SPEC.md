# Agent Architecture & Integration Framework (SPEC, pasted 2026-08-29)

Status: DESIGN SPEC for 8-agent global market sweep. Maps to Empire OS v3 agent fleet as follows.

| Doc agent | Live Empire OS module | State |
|---|---|---|
| Scout | neural_scout.py, crawler_agent.py, satellite_scanner.py, whale_finder.py | LIVE |
| Auditor | lead_grader.py, evaluation_product.py (8-agent eval), site_audits | LIVE |
| Messenger | mail_sender_agent.py + outbound_email_pipeline (Brevo, si_outbox) | LIVE |
| Creative | copywriting_agent.py, cinematic_lp_agent.py, ugly_banner_gen.py, local_spinner.py | LIVE |
| Monitor | metrics_exporter, email_events/email_opens/email_clicks tables, revenue_dashboard | LIVE |
| Optimizer | strategy_rank.py, ab testing in email pipeline (A/B tune commits) | PARTIAL |
| Closer | conversion_agent.py, sales_agent.py, proposals_engine_agent.py, crm pipeline | LIVE |
| Analyst | data_analysis_agent.py, last30days_agent.py, warehouse_report.py | LIVE |

Orchestration: doc proposes Redis/RabbitMQ message queue + K8s. Empire OS reality: systemd services + timers + SQLite outbox + hub API. Message-queue layer NOT built; not needed at current scale.

Doc targets: 1,760 companies across 88 markets, $10M+ revenue. Current live sweep: 8 cities x 11 industries framework exists in market sweep lanes (crawler-chicago, crawler-losangeles timers etc).

[Original pasted doc: full 8-agent architecture framework v1.0 — agent roles, 4 orchestration loops (Discovery/Engagement/Conversion/Optimization), message protocol, deployment/scaling phases 1-4, monitoring thresholds, failure handling. Full text in session transcript 2026-08-29.]
