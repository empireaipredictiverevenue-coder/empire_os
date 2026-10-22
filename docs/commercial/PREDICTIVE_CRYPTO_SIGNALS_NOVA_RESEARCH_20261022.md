# EmpireOS Predictive Cloud — proprietary cryptocurrency signal intelligence and stop-loss-first research

Date: 22 October 2026. Owner: existing Predictive Decision Control branch. Phase 1 is pure **OBSERVE/research**, not a signal subscription, portfolio manager, live exchange bot, DeFi trading agent or claimed 99%-accurate predictor.

## 1. Identification: "Nova Mind" is ambiguous, so do not claim cloned capabilities

The user's named "Nova Mind trading bot" cannot be definitively identified from the name alone. Research found:

- **NovaMind AI 5.0** announced by KapitalIntelligenz Akademie in September 2025: https://www.globenewswire.com/en/news-release/2025/09/03/3143904/0/en/KapitalIntelligenz-Akademie-Advances-NovaMind-AI-5-0-to-Final-Testing-with-Thomas-Bernhard.html . Publisher press release describes Trade Signal Decision Engine, AI-based algorithmic execution, strategic decision framework, expert advisory and adaptive market data models. No audited win rate, real stop execution proof, statistically independent forward trading results or publicly inspected source code were verified from this announcement. A subsequent distributor article described the platform as controlled testing and human-directed decision support: https://markets.financialcontent.com/wral/article/247pressrelease-2025-9-6-kapitalintelligenz-akademie-publishes-technical-evaluation-summary-for-novamind-ai-50-developed-by-thomas-bernhard
- **Nova (ainova.dev)**, different product: https://ainova.dev/ describes an elizaOS/Solana-native agent integrating DexScreener/pump.fun token momentum, wallet watchers, Jupiter routing, rug-risk screening, automated exits and character-config stop losses. Those website claims do **not** independently prove its realized return, protections, code quality or suitability to EmpireOS's BSC checkout. Copying or connecting an autonomous trading bot without risk and owner approval is out of scope.
- **nova-mind.live** uses the NovaMind name for an AI infrastructure-investment landing page with daily-returns language, not verified as the user-intended bot or a proven public quant strategy. Do not enter funds, credentials or connect Empire wallets on brand matching alone: https://nova-mind.live/

## 2. Commercial benchmarking — how established vendors actually package it

- 3Commas signal marketplace: subscribable third-party signal providers, optional mandatory stop loss, provider ranking with subscriber-bot P&L: https://3commas.io/crypto-signals . Its tiered automation/software plans and exchange/API limits are published at https://3commas.io/pricing . **A marketplace ranking is not universal proof of independent outcomes or future returns**.
- Cornix: structured Telegram/Discord signal entries, targets, stop/trailing orders, following channel providers and optional execution via exchanges. Commercial pricing includes Advanced, Premium, Asset Manager and Community Admin white-label plans: https://cornix.io/pricing/ ; https://help.cornix.io/en/articles/5814956-signal-posting ; https://help.cornix.io/en/articles/5814976-cornix-signals-vs-trades .
- Cryptohopper: tiered bot software, strategy designer/marketplace/backtesting, AI strategy combinations, multiple stop/trailing settings, paper trading: https://www.cryptohopper.com/pricing ; https://support.cryptohopper.com/en/articles/9010180-how-can-i-trade-with-the-trading-bot .

**Viable revenue hypotheses (NOT approved/public tariffs)**: subscription access to research-only dashboards and market-health analytics; separate enterprise licensing of an independently tested signal-data feed; and ultimately compliant provider/white-label integration only with full UK/US market-access review. Never equate software seat fees with audited profitable trading signals; never claim fixed returns, 99% accuracy, guarantee of stop execution or exchange affiliation. A UK-facing commercial signal may be a regulated cryptoasset financial promotion even if users execute manually; obtain specialist review of the exact product and distribution before marketing. FCA guidance: https://www.fca.org.uk/firms/cryptoasset-financial-promotions-and-fiat-crypto-ramp-services and https://handbook.fca.org.uk/handbook/perg18/perg18s8 .

## 3. Implemented proprietary research: Empire Regime-Risk Signals (ERRS v1)

Pure module: `empire_os/predictive_crypto_signal_research.py`.

- Supports completed, point-in-time available 5-, 15-, 60-, 240- and 1440-minute OHLCV series with strict market candle validity, original evidence-change hash, UTC source availability and ingestion times, chronological/regular sampling and stale-data rejection.
- Uses a long-only EMA12/EMA26 trend regime with 0.1% threshold, 10-completed-bar prior-high breakout, current volume at least 1.1x prior 20 bars, ATR14 as volatility scale, an ATR14/price admissibility range, and spread/fee/slippage gates. Other regimes return **NO_TRADE** rather than a short, borrow or leveraged position.
- Paper entry uses last completed close with spread impact; risk invalidation/stop is whichever is lower of 2x ATR below entry or prior six-bar low minus 0.25 ATR. Reject invalid stops and stops farther than 8% of entry.
- Maximum *modelled* nominal one-signal loss under stated fees/slippage is targeted at 0.5% of hypothetical quote equity, with quantity also capped to hypothetical unleveraged cash. A target models 2R gross plus cost allowance. There is NO real wallet, leverage, balance inspection, order placement or guarantee that an exit will fill at stop.
- Deterministic digest is for change detection, **not data ownership, exchange authentication or calibrated model confidence**. Signals are `PAPER_SIGNAL_CANDIDATE_NOT_VALIDATED` and are NOT advice or a live signal subscription.

`empire_os/predictive_crypto_stop_loss_simulator.py` evaluates the next completed bar as a deliberately conservative risk stress:
- Stop+take-profit touched in same OHLC candle => stop wins; do not infer favorable intrabar order.
- Gap beyond stop *before an attempted entry* => paper entry cancelled, not a fake trade.
- Gap beyond stop for a separately stipulated already-open **paper** position => unfavorable open less modelled adverse slippage; loss can exceed original planned budget. Real stop-market fills, stop-limit nonfills, outages, partial fills, liquidity and latency can be worse.
- Profit/loss are paper-only and deduct stated round-trip fees. This one-bar stress **does not** claim an out-of-sample trading backtest or historical alpha.

`empire_os/predictive_crypto_research_scorecard.py` separately calculates research-only positive outcome percentage, Wilson 95% lower bound, net P&L, profit factor, max drawdown and longest losing streak. It **never** upgrades research to `ninety_nine_percent_accuracy_validated=true` without independent outcomes. Test: 99 winners at +1 and one loser at -500 => **99% win rate but -401 net loss**, proving why win rate alone is insufficient.

Private CLI: `scripts/review_predictive_crypto_signals_20261022.py --read-only` reports the research capability; `--template` returns a blank owner-source format; `--series-file /original/data.json` evaluates only a locally supplied historical series under non-authoritative research status. No live exchange feeds have been connected.

## 4. Continuing "all aspects" roadmap for Predictive Cloud / learning

Enhance existing Predictive and Market GPS systems in deliberate evidence-gated waves:
1. **Original feed custody**: exchange venue-specific signed/verified completed OHLCV and order-book history, market tick sizes, maker/taker fee tiers, spread/depth by notional, asset delisting changes, outage and rate-limit evidence; stablecoin liquidity, trading pair funding and derivatives open interest; timestamped data rights and retention. Do not mix differently defined aggregate tickers or delayed futures/perpetual data.
2. **Crypto breadth**: majors and liquid spot pairs before illiquid microcaps. On-chain holder distribution, contract privileges, mint/pause/freeze, honeypot simulation, bridge/security risk, concentration, treasury unlocks, DEX pool depth, wash trading/spoofing, cascading liquidations and blockchain reorg risk are separate veto/research features—no unverifiable rug score sold as certainty.
3. **Regime ensembles and continual validation**: range/trend/high-volatility/stress/liquidity regimes, ATR vs realised volatility, order flow, momentum/reversal, moving average/volume, futures basis/funding, macro rates and news lag. Each forecast trained using original historically available inputs, walk-forward test splits, baselines and multiple-hypothesis corrections. Paper learning is a versioned offline experiment, not online self-changing money logic.
4. **Execution simulator**: stop-market and stop-limit semantics per venue; fills, partial fills, maker/taker fees, gas on DeFi, funding, spreads, MEV, outage/gaps, queue position, stop-trigger and target-hit order within ticks. Conservative OHLC defaults until tick data proves actual chronology. Include total portfolio exposure, correlated losses, drawdown circuit breaker, risk-off and never widen stops to evade loss.
5. **Performance and safety**: publish only exchange/ledger-verified, out-of-sample results with sample sizes, event definitions, rejection/abstention frequency, unconditional and conditional precision, realised P&L after costs, max drawdown, VaR/CVaR limits, calibration and failures; stop-hit rate, stopped-out gap risk, untouched target, missed fills and false positives.
6. **Regulatory distribution**: UK/US licensing and promotional perimeter review, market-specific terms and security, no client wallet custody or live margin authority without reviewed agreements. Any premium research dashboard or commercial signal product needs separate founder/legal sign-off.

Academic warning: walk-forward crypto ML trading analysis finds that gross apparent performance can fail after fees; a rigorous cost-aware execution filter is important: https://arxiv.org/abs/2606.00060 . A 2026 crypto factor audit warns about multiple backtests and inflated naive Sharpe: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7350238 .

## 5. Release boundaries

- No 99% claim, winner cherry-picking, automatic model weights, real signal broadcasts, live orders, exchange API credentials, wallets, margin, DEX Jupiter or BSC transactions.
- No customer-forecasts or revenue validation: the independent original conversion prediction registry in EmpireDB is still absent at the authenticated check. Market prediction confidence is not customer conversion probability.
- Private release only after full tests, static source manifest and read-only CLI smoke checks; Cloud's `future_trend_latest.json` remains explicitly `analysis_executed=false` until original source admission.
- Require original independently admitted market data, true venue-specific cost and trading rules, historical rolling evaluation and market/regulatory review before any subscription or trade-distribution launch.

**Result:** ERRS v1 is original research implementation, **not** a 99%-accurate product or a trading bot connected to crypto markets.
