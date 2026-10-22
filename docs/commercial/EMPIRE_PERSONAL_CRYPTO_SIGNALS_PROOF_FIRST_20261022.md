# EmpireOS — private personal crypto signals, proof first, then assess selling

Date: 2026-10-22. Dedicated engineering branch: feature/predictive-crypto-personal-proof-20261022.
Original feature branch and production sources intentionally untouched to avoid concurrent-agent worktree collisions.

## Goal and absolute gates
Owner's personal crypto signal research FIRST, commercial signal distribution only if separately justified much later. **99% future signal accuracy cannot be guaranteed**. A high historical win fraction is not evidence of durable, net-of-cost positive expectancy, correct stop fills, truthful model probabilities or independent unseen performance. An unverified live paper-test with zero closed trades cannot be called a result.

## Existing EmpireOS ERRS proprietary algorithm
The existing `empire_os/predictive_crypto_signal_research.py` produces **LONG spot WATCH research / NO_TRADE** based on completed candles, EMA12/26 trend regime, 10-bar breakout, volume expansion and 14-period ATR. It applies spread, modeled round-trip fees, stop-exit slippage and volatility gates. Original ATR + swing-low stop-loss is mandatory. Paper position size aims to risk at most 0.5% of hypothetical quote equity at modeled stop, with 2R approximate profit target and clear warning that market gaps can exceed stop and paper risk budget.

The existing `predictive_crypto_stop_loss_simulator.py` pessimistically resolves ambiguous stop+target touches as stop, and marks worse-than-stop gaps. The existing `predictive_crypto_research_scorecard.py` measures positive paper returns vs net expectancy, profit factor, absolute drawdown, losing streak and a 95% Wilson lower bound; even 99/100 winners and one catastrophe can lose money. No result is an independently measured execution receipt.

## NEW: independent branch personal walk-forward evaluator
`empire_os/predictive_crypto_paper_walkforward.py`:
- Requires 100+ complete, exactly regularly spaced candles and a recent original as-of; all input market custody remains untrusted until independently sourced.
- Keeps ERRS algorithm and fixed settings unchanged: first 70% of chronological bars precede a held-out last 30% evaluation interval. Replays **only historical prefix available by each decision time**; no current/future candle features are seen.
- **Does not fill on the first candle open immediately after the signal**, which occurs before the completed signal is ingested. Delays paper entry until a later candle, and cancels when price has moved too far or breaches the stop/target.
- On accepted paper open, models buy slippage+half-spread and recalculates risk-position size. Sequential single spot position, no overlapping leveraged trades. Exit is conservative: gap-open through stop at worse market price, same bar stop+target -> stop, modeled fees, max 24-bar exposure, and no false win when future bars are **right-censored**.
- Paper research stops after an assumed 2% initial-equity drawdown or 3 consecutive losses. This is not a guarantee about what an exchange would do: gaps, latency, liquidity, partial fills, failure to execute and venue risks remain.
- Evaluations with fewer than 100 independent closed held-out paper outcomes do not qualify as a basis for a meaningful performance claim. Even more trades would need prospective independently reconciled paper receipts, reliable costs, venue fills and multi-regime testing.
- Carries status `PERSONAL_WALK_FORWARD_PAPER_ONLY_NOT_VALIDATED`, `sale_of_signals_approved=false`, `model_auto_training_or_optimization_used=false`, `exchange_orders_authorized=false`. It is not a trained adaptive ML model yet.

## Private release
`scripts/review_predictive_crypto_personal_20261022.py`: `--capabilities`, `--template`, `--paper-file ORIGINAL.json` and `--walkforward-file ORIGINAL.json`, always `--read-only`. Optional source fields must remain explicitly false; callers cannot claim independently verified market feed, commercial licence or regulated advice by setting JSON fields.

`scripts/prepare_private_crypto_personal_release_20261022.sh` builds an immutable, SHA-pinned private checkout containing only signal research, scorecard, personal paper-walkforward and bounded CLI. Does **not** install an executable order client, exchange credentials, systemd timer, market feed, API or service. New dedicated private alias `empire-crypto-personal` verifies release commit and checksums; no production Cloud or shared Predictive worktree changes.

## Research comparison: what providers actually sell
- **3Commas** operates a marketplace for third-party signal providers and bot configurations; plans and signal performance vary. It says marketplace min/max P&L can come from user-bot outcomes rather than provider self-reported percentages. https://3commas.io/crypto-signals
- **Cryptohopper** lets third-party signalers send custom stop, target and trailing-stop settings. https://docs.cryptohopper.com/docs/marketplace/what-are-signals/
- **Cornix** distinguishes a theoretical signal (entry/target/stop) from actual placed exchange orders, supporting both manual and bot-followed actions. https://help.cornix.io/en/articles/5814976-cornix-signals-vs-trades and https://help.cornix.io/en/articles/5814956-signal-posting
- **Nova Mind** exact trading bot identity, official public code/strategy and audited live performance could not be independently corroborated by the available public search. Other products named Nova / Nova AI are not automatically the same service. Do NOT copy or credit a proprietary algorithm without verifiable reference.

## Broader research roadmap, NOT deployed
1. Authenticated, permitted original market data ingestion and prospective timestamped ledger: spot 1h/4h/daily for BTC, ETH and selected liquid pairs; exchange-specific spreads, order book depth and historical funding if allowed.
2. Per-market volatility, ATR gap distribution, volume/market-impact risk, market closures/delisting, flash crashes, drawdown guardrails, portfolio correlations, liquidity and exchange outage risk.
3. Regime classification for trending/ranging/choppy/risk-off, separate mean reversion and momentum candidates with frozen parameter versions; prevent selection overfitting.
4. Crypto on-chain evidence: token supply/unlocks, holder concentrations, contract vulnerabilities, stablecoin peg changes, bridge/layer-2 risks, DEX pool depth, MEV and slippage. No unrestricted crawling or data-rights assumptions.
5. Derivatives intelligence: futures funding rate, open interest, basis, liquidations and leverage mechanics for risk monitoring ONLY. No live margin or leveraged trading authorization.
6. Macro/news/security: BTC-ETH cross-correlation, dollar/rates, sentiment/attention, exchange incidents and project hacks; only source-authenticated first-availability series, not rumor-generated buy recommendations.
7. Walk-forward/embargo model experiments (traditional and ML), strict baseline comparison, multiple-strategy selection correction, realistic fees/spread/slippage/latency; immutable original predictions and prospective outcome reconciliation. Never claim 99% probabilities unless externally calibrated, with adequate tests.
8. Owner-private notifications/alerts after prospective paper audit; personal manual trading only after evidence/appropriate risk review. Automatic live orders separate explicit future approval.

## Later selling — separate commercialization decision
First require prospective, independently logged trades across sufficient bull, bear and sideways periods; provider-adjusted fees, funding, failed/cancelled trades, volatility gaps, maximum drawdown, return concentration and full stop-risk receipts. Customer-facing price or performance claims may need a statutory regulatory, UK FCA marketing and investment-advice perimeter review. Selling signals can constitute cryptoasset financial promotions depending on exact form and audience. No paid signals, subscriptions, Telegram channel, exchange execution or outreach now.

Sources:
- UK FCA: https://www.fca.org.uk/firms/cryptoassets ; https://handbook.fca.org.uk/handbook/perg8
- Kraken API: https://docs-legacy.kraken.com/api/docs/guides/global-intro/ (commercial use of public market data may require permission)
- CoinGecko licensing: https://support.coingecko.com/articles/1043089972-what-are-the-differences-between-commercial-and-custom-licenses (redistribution separate from standard commercial access)
- Walk-forward and costs: https://arxiv.org/abs/2609.34510 ; https://arxiv.org/abs/2606.00060

**Integrity boundary:** Source hashes detect changes, not original owner signatures. No trading claims until independently validated and no merchant or financial permissions are changed by this release.

## Optional one-shot founder-private public spot snapshot

A new strict `empire_os/predictive_crypto_kraken_personal.py` adapter makes a single HTTPS **public GET** to Kraken's spot OHLC endpoint for only BTC/USD or ETH/USD, at 1-hour intervals. It never accepts API keys or account tokens, and does not call trading endpoints. `empire-crypto-personal --btc` / `--eth` merely shows a research candidate or NO_TRADE as of the fetched completed candle, with a mandatory modeled stop and hypothetical position size; it is not a broker order or an instruction to trade. Kraken says its final OHLC entry is still forming, so the adapter always drops it and rejects stale/inconsistent remaining bars.

**Critical source custody:** Every historical bar is stamped first-available/ingested at the *actual fetch time*. We will not invent its original historical availability, so the live snapshot **cannot be presented as a point-in-time historical walk-forward result**. True proof needs prospective original snapshot retention, venue costs and receipts. No feed is scheduled and market-data redistribution is not authorized. Kraken's public endpoint access is subject to its terms; non-personal commercial uses may require prior approval. Source: https://support.kraken.com/articles/360000919986-public-endpoint-examples-you-can-try-them-directly-in-a-web-browser- and https://docs-legacy.kraken.com/api/docs/guides/global-intro/.
