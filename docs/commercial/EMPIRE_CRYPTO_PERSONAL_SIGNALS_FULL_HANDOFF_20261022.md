# EMPIREOS — PERSONAL CRYPTO TRADING SIGNALS: VERIFIED HANDOFF
Date: 22 October 2026, Europe/London
Owner: existing EmpireOS Predictive Intelligence + Predictive Cloud
Purpose: founder-only **private research and paper signals**, not a signal-selling product, order execution service or investment guarantee.

## 1. Canonical environment and branch custody

- Production: /srv/empire_os, canonical **EmpireDB PostgreSQL**, never Supabase.
- Existing primary Predictive branch: feature/predictive-decision-control-20261018
- Existing shared worktree: /home/ubuntu/empire_agents/predictive_decision_control_20261018
- Last independently tested clean crypto implementation commit: **aa55ef91f52dd6371ae0fff07b4cb7289db85b71**
- Crypto v1 private immutable release: /home/ubuntu/empire_releases/predictive_observe_aa55ef91f52d
- Private operator: /home/ubuntu/empire_releases/predictive_observe_aa55ef91f52d/bin/empire-predictive-observe
- Trends previous release: c73140d67245bac561128cd8f7b77e81616cc709; private shortcut /home/ubuntu/.local/bin/empire-predictive-trends
- This handoff was drafted in isolated worktree /home/ubuntu/empire_worktrees/crypto_personal_signals_handoff_20261022 on feature/crypto-personal-signals-handoff-20261022. Do not mix this isolated handoff branch into the shared dirty implementation tree without conflict reconciliation.

## 2. VERIFIABLE tested state

- At aa55ef91f, the four crypto-specific test modules gave **46 passed** in an isolated checkout.
- Expanded compatibility suite with Predictive Cloud, temporal features, registry and ASTRA review gave **204 passed**, one existing Starlette/AnyIO deprecation warning.
- The aa55ef91f immutable release's critical SHA-256 source manifest passed.
- Read-only release commands **crypto** and **crypto-template** executed successfully from that pinned release.
- The release prints PRIVATE_OBSERVE_PAPER_SIGNAL_RESEARCH_AVAILABLE, algorithm EMPIRE_REGIME_RISK_SIGNALS_V1, mandatory stop loss TRUE, 99_percent_accuracy_promise FALSE, and live_orders_or_margin_authorized FALSE.
- No real original OHLCV exchange feed was admitted; no live trading signals, measured trading accuracy, actual P&L, authenticated fills, subscriptions or wallet action were proven.
- Founder API and Predictive Cloud timer were active/success at earlier inspection. No deployment of the crypto engine into the live Cloud service or Founder Console was confirmed.

## 3. Existing proprietary first-party algorithm (do NOT rebuild)

Use these exact tracked baseline files at commit aa55ef91f:
- empire_os/predictive_crypto_signal_research.py — proprietary Empire Regime-Risk Signals v1 (ERRS), completed-candle ingestion and decision-time filtering, EMA12/EMA26 market regime, completed 10-bar high breakout, 20-bar volume confirmation, ATR14 volatility gate, spread/fee/slippage guards. Applies long-only paper candidate or NO_TRADE, no probability claim.
- empire_os/predictive_crypto_stop_loss_simulator.py — deterministic one-candle stop-risk simulator. Stop-first if both target and stop are touched, adverse gap fill and slippage stress, no guarantee of fill.
- empire_os/predictive_crypto_research_scorecard.py — bounded paper outcome scorecard: count, win fraction, Wilson 95% lower bound, mean/total net P&L, profit factor, drawdown, loss streak. Retains false flags for independent live validation and 99% certainty.
- scripts/review_predictive_crypto_signals_20261022.py — read-only private capability report, empty original candle intake template, bounded research on user-supplied JSON.
- tests/test_predictive_crypto_signal_research.py, tests/test_predictive_crypto_stop_loss_simulator.py, tests/test_predictive_crypto_research_scorecard.py, tests/test_review_predictive_crypto_signals_cli.py — committed verified v1 tests.
- scripts/prepare_predictive_readonly_release_20261020.sh — existing immutable release builder, including crypto and crypto-template modes at aa55ef91f.

ERRS v1 preliminary paper policy: instrument is user-declared (no data/exchange authority inferred), supported timeframes 5/15/60/240/1440 minutes, at least 35 completed original candles, current recent source, EMA fast/slow rising, breakout and volume confirmation, ATR range 0.3%-8%, spread at most 25 bps, total friction at most 100 bps; otherwise NO_TRADE. Paper stop is the more conservative of 2 x ATR or previous swing-low buffer; gross target 2R plus friction. **0.5% of hypothetical quote account equity maximum modeled risk per candidate**, capped by available cash; stop fills may exceed that cap under gaps. NO leverage, short selling, subscriptions, order placement or automatic training.

Private read-only verification, which was ALREADY executed successfully:
  /home/ubuntu/empire_releases/predictive_observe_aa55ef91f52d/bin/empire-predictive-observe crypto
  /home/ubuntu/empire_releases/predictive_observe_aa55ef91f52d/bin/empire-predictive-observe crypto-template
Do not ask the founder to run these when the connected operator can.

## 4. CRITICAL CONCURRENT-WORKTREE ISSUE — resolve FIRST

The main shared worktree advanced to aa55ef91f while a separate concurrent crypto developer/editor began a new walk-forward extension. At inspection it contained these UNCOMMITTED changes:
  M empire_os/predictive_crypto_signal_research.py
  M scripts/prepare_predictive_readonly_release_20261020.sh
  M scripts/review_predictive_crypto_signals_20261022.py
  M tests/test_predictive_crypto_signal_research.py
  M tests/test_review_predictive_crypto_signals_cli.py
  ?? empire_os/predictive_crypto_paper_walkforward.py
  ?? tests/test_predictive_crypto_paper_walkforward.py

The combined dirty-tree test run failed at COLLECTION: walkforward imports _time/_value/review_crypto_trade_signal expected from ERRS baseline, but current working-file edits changed the interface. The CLI tests import baseline tests' bars/START/PARAMS, but the dirty edited test file lacks bars. This is a **concurrent interface conflict, NOT a proven defect in immutable aa55ef91f**. Do not claim the uncommitted walk-forward extension works or has been deployed. Do not delete or git-reset someone else's edits blindly. Inspect current git status and all writers; have one owner integrate modules against aa55ef91f in an isolated branch, preserve provenance, run all tests, then merge in a coordinated change.

The uncommitted walk-forward design appears promising and should be reviewed, not silently discarded: delay paper entry until the actually next AVAILABLE open (avoid fictitious immediately-next-candle fills), conservative stop-first OHLC paths, worse-than-stop gap risk, no chase, right-censor unfinished horizons instead of labeling them winners, sequential non-overlapping paper positions, 70/30 chronological split, fees and slippage, 2%-drawdown/three-loss-streak research breakers, and Wilson scorecard. Its code was NOT independently integration-validated at handoff.

## 5. Research: Nova Mind and third-party signal product patterns

Requested brand **"Nova Mind trading bot"** could NOT be positively identified from verified official sources. Do not invent a Nova Mind strategy, account, audit or performance. A distinct project at https://ainova.dev/ calls itself Nova (autonomous Solana/pump.fun/DexScreener/Jupiter) and advertises momentum, wallet tracking, rug scores and automated stop exits; identity with requested Nova Mind is UNPROVEN. Never copy its unaudited execution strategy or turn on Solana trading merely because the research source mentions it.

Primary vendor/research references checked Oct 22, 2026:
- https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/ — alert delivery to private webhooks; no secrets in payload.
- https://3commas.io/features — concurrent TP/SL, trailing stops, partial targets, signal management.
- https://help.3commas.io/en/articles/17674079-how-best-bid-ask-limit-orders-work — conditional stop-limit can fill badly or not at all; market stop has execution-price risk too.
- https://docs.cryptohopper.com/docs/marketplace/what-are-signals — third-party signals with configurable stop/take-profit/trailing.
- https://www.cryptohopper.com/marketplace — marketplace signals/templates/strategies priced as subscriptions or small per-signal offerings (not proof of effectiveness or demand for ours).
- https://coinrule.com/crypto-trading-bots/stop-loss/ — rule-based and portfolio stop policies.
- https://www.coinbase.com/en-gb/legal/trading_rules?locale=en-US — stop-limit may not fill.
- https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/key-concepts — backtesting requires execution friction/slippage models.
Regulatory/commercial caution: signal-selling/marketing in the UK should undergo FCA/crypto-financial-promotion and investment-advice review before ANY public or subscription offering. **Founder explicitly said signals are for his personal use. Do not build a marketplace or sell anything now.**

## 6. Desired broad crypto/trading intelligence coverage (ROADMAP, not shipped)

Extend existing Predictive Cloud and Future Trend infrastructure, NOT a new random autonomous bot:
A. Market structure: spot OHLCV, quote spread, depth/impact, volume/liquidity, multi-timeframe regimes (trend/range/breakout/reversal), volatility, correlations and market breadth.
B. Derivatives WATCH-ONLY: futures basis, perpetual funding, open interest, liquidations, leverage crowding and liquidation cascades. Do not place leveraged orders.
C. On-chain: exchange inflows/outflows, holdings concentration, whale/smart-wallet movements, stablecoin mint/burn and reserves, bridge conditions, gas fees, staking/unlocks, DeFi lending and oracle risk. Authenticate sources and labels; cluster heuristics are NOT identity proof.
D. Security and tokenomics: contract permissions, honeypot and rug risk, unlock schedules, vesting, liquidity pool depth/locks, bridge exploits, MEV, depegs, downtime/outage status, scams. Default abstain on missing safety evidence.
E. Real-world/macro: interest rates, CPI, USD liquidity, risk-on/off proxies, regulatory decisions, economic events, accepted breaking news, weekend liquidity.
F. Learning/evaluation: walk-forward and embargoed OOS, data rights, timestamps, source revisions, normalisation, trading costs, venue outages, regime-specific results, survivorship bias, multiple comparisons, drift monitoring, economic/technical incident post-mortem and source memory.
G. Risk controls: per-trade, per-day, per-week and portfolio risk ceilings; stop market vs stop-limit trade-offs; a stop-loss breach log; partial fills, gaps, disconnects, volatility circuit breakers; optional future breakeven/trailing rules only after independent tests and bounded position authority.
H. Private delivery: founder-authenticated signed alerts, signal expiry, evidence snapshot, indicative entry/risk/SL/TP, confidence as calibrated probability ONLY with genuine sufficient trials, paper journal and human review. Never auto-trade at first activation.

## 7. Accuracy policy: 99% is a target, NEVER a promise

An indicator score of 99/100 is NOT a 99% win probability. Even 99/100 wins can lose money if the 1 loss overwhelms the gains. Never optimise to a tiny cherry-picked signal sample or declare that abstention alone creates accuracy. Report:
- Candidate frequency and NO_TRADE/ABSTAIN frequency.
- Number of independent completed, net-of-fees paper trades and distinct market regimes, plus data/source rights.
- Positive net-trade fraction, 95% Wilson lower bound, expectancy, median win/loss, net profit factor, drawdown, max stop breach, coverage.
- Strict chronological OOS walk-forward (no future data at candidate time, no fill at a price already elapsed before signal became available); multiple symbol/timeframe/market regimes; realistic maker/taker fees, spreads, adverse slippage, latency, gaps and exchange downtime.
- Benchmark vs buy-and-hold, naive alternatives and dummy/no-trade policy; avoid overfitting to many tests.
- Independent broker/exchange fill receipts before claiming live performance or 99% precision. ANY scorecard without authentic fills remains a paper hypothesis.

## 8. Explicit security/production boundaries

Always keep: OBSERVE default, live orders OFF, wallet custody OFF, API trading permissions OFF, leverage and liquidation OFF, public signal marketing OFF, real funds OFF, model auto-training OFF, automatic paper score promotion OFF, no new DB roles/grants and no alternate Supabase database. Existing BSC/USDT **payments** are an unrelated flow; never reuse BSC payment signing keys or escrow functions to trade.

All market data must have original timestamps (close, first availability, ingestion) and independent source authentication/usage rights before promotion. No invented fresh prices, sample counts, venue fees or model confidence. Report failures, no-data and exchange outages as HOLD/NO_TRADE, not zero risk. STOP LOSS IS NOT GUARANTEED—gaps and slippage can exceed the planned 0.5% research budget. No paid traffic/subscriptions/dependencies without founder authority.

## 9. Exact next-agent ordered plan

1. Inspect current shared worktree branch/head/dirty status and find who owns the concurrent edits; DO NOT reset them. Pin a clean isolated integration branch from aa55ef91f.
2. Reconcile baseline ERRS v1 APIs with the in-progress walk-forward runner/CLI/tests or preserve the uncommitted extension in a separate coherent patch; ensure a single schema and no duplicate engine.
3. Address **paper execution timing**: if a signal is known only after its source was ingested, never use a prior opening price. Test next-available open, entry cancellation, right-censoring, stop-first ties, gap losses beyond risk, loss streak and 2% research circuit breaker.
4. Run crypto-specific and neighboring Predictive/Cloud suites, along with a fixed synthetic offline OHLCV gauntlet, but never market synthetic results as genuine hit rate. Verify code checksum, build private immutable OBSERVE release, pin operator shortcut without changing production services.
5. Obtain legal, free and correctly licensed read-only market history from existing source owners (public OHLCV from an exchange/public first-party channel). Preserve venue/market identity and original available/ingested timestamps. No exchange API trading permissions.
6. Produce first honest ETH/BTC/SOL spot paper research report with NO_TRADE default and historical OOS net-of-cost outcomes. Validate trends/current/future trend source confluence separately.
7. Only if evidence warrants, mount a private authenticated Founder Console panel, with alert audit, trade journal and expiry. No real trades by automation, funds, margin or commercial subscriptions.
8. Independent ASTRA GPT-6 challenge and founder approval are later, separate gates. Work towards genuine empirical performance; reject unsupported 99% claims.

## 10. Ready-to-paste instructions for the next agent

"Take ownership of EmpireOS founder-private crypto signals and trading intelligence. Start from tested committed baseline aa55ef91f52dd6371ae0fff07b4cb7289db85b71 on feature/predictive-decision-control-20261018. Read this handoff. DO NOT rebuild the existing Predictive Cloud, future trend system, ERRS crypto research algorithm, stop-loss simulator or scorecard. Before changing the shared worktree, inspect concurrent uncommitted changes in predictive_crypto_paper_walkforward.py, the crypto CLI, release launcher and crypto tests; coordinate one owner and reconcile in an isolated worktree. Run the crypto suite, repair next-available-open lookahead, simulate costed stop/gap risk with stop-first semantics and right-censor unfinished trades, then commit/push a clean immutable private OBSERVE-only release and deliver a paper scorecard. Research broad spot, derivatives, on-chain, token security, macro and market regimes as source-labeled inputs. Signals are for the founder's personal decision-making, not for selling. Stop-loss is mandatory, may slip; never claim 99% without independent time-split and actual fills. Do not enable trades, exchange API trading keys, wallet transfers, payment keys, leverage, DB grants or production financial action. Use the connected EmpireOS operator to run commands; ask the founder only when an actual privileged or binding approval gate requires it. Give exact commit and test receipts, fail-closed holds and next actions."
