# Empire AI Predictive Revenue — enterprise competitor evidence benchmark
2026-11-15 | Existing EmpireOS / Predictive Revenue / Smart CRM / JEV owners
Status: research-backed benchmark, NOT product parity or customer-proven superiority.

## What competitors offer (vendor-sourced, not independently tested)

| Competitor | Verified marketed capability | Evidence | Empire AI observable gap |
| --- | --- | --- | --- |
| Salesloft/Clari | Clari forecasting and deal inspection linked to seller tasks, AI follow-up and MCP-governed AI access to live revenue intelligence. | https://www.salesloft.com/company/newsroom/clari-salesloft-forecasting-execution-mcp-server ; https://help.salesloft.com/s/article/Enable-Clari-Forecast-MCP-in-Clari-Studio | Existing JEV + typed decision report currently recommendation-only; no verified customer closed-loop action/forecast improvement. Preserve founder outbound approval. |
| Gong | Deal forecasts and likelihood powered by history, pipeline and conversation signals, plus AI-suggested deal updates and deal boards. Its forecast documentation cites approximately 400 opportunities, 150 wins and four quarters as a reliable-projection threshold for its setting. | https://help.gong.io/docs/analyze-see-forecast-projection ; https://help.gong.io/docs/understanding-deal-boards | Zero independently admitted customer forecast/outcome pairs; no defensible head-to-head precision or Brier/calibration comparison. The 400/150 threshold is vendor guidance, not a universal requirement. |
| HockeyStack | Joined first-touch-to-closed-won buyer journeys, multi-touch attribution, incremental lift reporting, CRM sync and forward-looking AI actions. | https://www.hockeystack.com/ ; https://www.hockeystack.com/about | Search Fabric + Smart CRM must establish consented first-party identity and independently verified closed-revenue joins before attribution claims. |
| Productive | Agency job/budget and tracked-time profitability, resource utilisation, long-horizon scenario and revenue forecasting. | https://productive.io/ ; https://productive.io/profitability/ | Need genuine agency cost/hour, project, invoice and margin integrations—not another project-management platform or guessed profit figures. |
| Aviso | Pipeline and account inspection, opportunity/engagement, historical forecast/attainment, and next-best-action views. | https://www.aviso.com/product/deal-pipeline-inspection | Existing predictive JEV evidence/reasoning must be connected to measurable, consented sales outcomes, with executive review and auditable overrides. |

## Positioning to test, not claim

**Customer wedge:** UK/US agencies or revenue operations teams who already use a CRM and want to identify which **marketing/source → qualified opportunity → paying customer → retained margin** motions work. Enterprise deal coaching is a separate, longer sales-cycle buyer cohort; do not collapse the two ICPs.

**Proposed differentiator:** An evidence-governed decision layer that connects Search Fabric source provenance, Smart CRM identity and sales, Predictive Revenue forecasts, finance-verified actuals and JEV next-action recommendations. The value proposition is **fewer untrusted numbers and faster measured corrective action**, not “100% more accurate” or an unsupported forecast claim.

## Minimum objective competitor benchmark for this existing department

1. **Time-to-value & reliability:** Baseline a real opt-in agency CRM + analytics read-only connection, median time to first useful report, source freshness, missing-field rate and verified tenant-isolation failures. Current 7–10s runtime-file scan is a diagnostics speed metric, **not** a customer forecast latency metric.
2. **Forecast precision, calibration & accuracy:** Only cohort original immutable pre-outcome forecasts with independently settled and complete mature-day customer actuals. Hold all confidence claims at N=0. Reuse existing enterprise scorecard; compare MAE/wMAPE for revenue amount, Brier/reliability curves for probability where available, interval coverage, and precision@K for prioritisation. Use strictly earlier training data, untouched forward holdout, segment/horizon disaggregation and an honest historical baseline. Internal 12+ pairs starts a *diagnostic*, not a statistically credible claim of beating Gong.
3. **Decision quality:** For each authorised JEV recommendation, capture timestamp, evidentiary source, counterfactual alternative, expected outcome, operator decision, execution receipt and final observed result. Track acceptance, false alarms, time to action, revenue/margin impact, and audit trace. No auto-send/payment/spend.
4. **Agency-specific outcomes:** Connect actual time costs, supplier costs, client invoice status, contract/retainer duration, utilisation, and revenue leakage **through existing APIs**, and compare project-margin forecast against actual margin. Keep source invoice and recognized-revenue distinct.
5. **Commercial proof:** Qualify at least one genuine agency pilot, then repeat on independently onboarded cohorts. Test which evidence-led recommendations improve verified enquiries or net margin relative to no-action/control before making superiority statements.

## Current measured state, 2026-11-15

- First-party EmpireDB catalogue: original per-event reader and trusted tenant resolver exist; forecast registry and daily census function missing from production at last founder read.
- REV076 native registry and REV077 native source census are **staged and isolated-test verified**; neither production DDL is applied.
- Original JEV research feed observed with zero model calls; operational evidence inference cannot substitute for customer outcome labels.
- Verified original customer forecast/outcome pairs: **0**. Independent financial proof categories unadmitted: **7**. No statistically defensible customer forecast calibration or rival accuracy comparison.
- EnterpriseDB backup status: encrypted local pgBackRest copies observed, but independent off-node backup/PITR/failover verification not yet complete. Enterprise deployment claims remain held.

## Interpretation standard

Vendor sites document product capabilities, not independent head-to-head quality. We must not claim to be better than a competitor until a blinded and comparable buyer cohort shows improvement in **actual customer outcomes, total implementation cost, forecast accuracy and decision timeliness**, with errors and counterexamples published internally. Existing departments own follow-through; no duplicate CRM, Search Fabric, forecaster or website is authorised by this benchmark.
