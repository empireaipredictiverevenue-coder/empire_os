# Agent Architecture & Integration Framework (ARCHIVED SPEC v1.0, 2026-06-27)

Founder-provided design doc archived 2026-08-29. 8 agents, 4 orchestration loops, message-queue comms, target $10M+ revenue.

## The 8 agents
1. Scout — market intel, fleet verify (satellite), WHALE tagging (10+ trucks), daily 6AM UTC, 20 companies/hour, 95% accuracy
2. Auditor — personalized efficiency audits, portal link + 30-day token, <10 min/audit
3. Messenger — cold email via Resend, 95%+ delivery, open 25-35%, portal click 40-50%
4. Creative — personalized audit portals (logo, case studies, ROI calc), <15 min/portal
5. Monitor — real-time campaign metrics, anomaly alerts, <5s latency
6. Optimizer — A/B testing 24-48h cycles, 95% significance
7. Closer — demos, proposals, 30-90d sales cycle, $100K-$500K deals, 20-50% close
8. Analyst — weekly/monthly aggregation, CAC/LTV/ROI, insights

## 4 loops
- Discovery: Scout->Auditor->Messenger->Monitor (daily). Feedback: delivery<90% alert scout; open<25% fix subjects; click<40% fix portal
- Engagement: Creative->Monitor->Optimizer (on portal visit). Scroll>70%, CTA>40%, demo req 5-10%
- Conversion: Closer->Monitor->Optimizer (on demo). 20-50% close, 30-90d, $100K-500K avg
- Optimization: Analyst->Optimizer->All (weekly). CAC $15K->$8K, conv 10%->25%+

## Message queue format
JSON-RPC style: message_id, sender, recipient, message_type (company_data|audit_data|email_sent|portal_created|engagement_data|optimization_recommendation|deal_update|analysis_report), priority, data, retry_count, max_retries=3, timeout.

## Empire OS v3 live mapping (2026-08-29)
- Scout -> neural_scout.py + crawler_agent.py + scout_agent.py (empire-neural-scout.service running; crawlers chicago/la timers)
- Auditor -> lead_scoring.py + aeo_checker.py + evaluation_product.py
- Messenger -> mail_sender.py (empire-mail-sender.service, Brevo backend) + email_agent.py + outreach_runner.py
- Creative -> aeo_generator.py + content_engine.py + avatar pipeline
- Monitor -> metrics_exporter.py + empire-health-* timers + revenue_dashboard.py + dashboards
- Optimizer -> email A/B tuning (commit fca116a) + marketing_dspy.py + agi_marketing.py
- Closer -> conversion_agent.py + crm.py + si_buyer_outreach.py
- Analyst -> data_analysis_agent.py + daily_report + predictive_revenue.py
- Queue -> hub lanes (empire-lanes.service) + agent_registry table + feedback/*.jsonl, not Redis
Gaps vs spec: Vapi AI calling NOT wired in v3 hub; k8s/Redis/Elasticsearch replaced by incus+systemd+SQLite+jsonl (per founder infra prefs).
