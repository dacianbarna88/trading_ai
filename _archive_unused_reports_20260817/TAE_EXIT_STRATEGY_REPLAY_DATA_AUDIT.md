# TAE Exit Strategy Replay — Data Audit (READ_ONLY)

**Generated for extension of commit `8c21634`**  
**Mode:** READ_ONLY | NO_BROKER | NO_LIVE_PROMOTION

## Verdict

**`SMALL_BAR_REPLAY_ADAPTER_REQUIRED`**

## Why not EXISTING_BAR_REPLAY_REUSABLE

| Source | Has ordered bars post-entry? | ATR14 / EMA20 / EMA50 causal? | Same BUY cohort? |
|--------|------------------------------|-------------------------------|------------------|
| `runtime_outputs/tae_intraday_fade_history.csv` | No — one OHLC snapshot per observation | No | Partial (open positions only) |
| `tae_profit_protection_validation.py` | Aggregates fade snapshots only | No | N/A |
| Snapshot `BASELINE_FIXED` in `tae_exit_strategy_comparison.py` | Intraday high→current path only | No | Fade cohort |
| `core/trailing.py` | Production live path | N/A | Live only — must not modify |
| `research_core/strategy_simulation/historical_backtest_runner.py` | Yes (OHLCV via MarketDataService) | Yes via `enrich_ticker` | Different entry universe (discovery), not portfolio BUYs |

Fade history alone cannot support no-look-ahead ATR/EMA/trend comparison without inventing bars.

## Why not DATA_INSUFFICIENT

Canonical bar history is available via existing research market data:

- `research_core.services.market_data.MarketDataService.download()` → `download_history()` (yfinance daily OHLCV)
- `research.momentum.context_intelligence_research_v18.compute_atr` — Wilder ATR14
- Portfolio entries in `portfolio.csv` provide ticker, entry timestamp, entry price, shares (READ_ONLY)

Minimal missing piece: a **small adapter** that joins portfolio open BUYs to post-entry daily bars and evaluates A/B/C/D causally.

## Canonical indicator sources reused

| Indicator | Source | Notes |
|-----------|--------|-------|
| ATR14 | `compute_atr` (research canonical) | Causal EWM; warmup until period bars |
| EMA20 / EMA50 | Adapter `ewm(span=N)` on Close | Deterministic; not previously used for exit |
| Trend state | `EMA20 >= EMA50` → POSITIVE else NEGATIVE | Challenger rule; two-bar confirm for sell |

`core/indicators.py` has only RSI + last price — **not** used as ATR/EMA authority.

## Fields available for replay

From `portfolio.csv` (read-only): ticker, Date (entry), Price (entry), Shares, Action.  
From OHLCV download: Open, High, Low, Close, Volume, timestamp index.  
Derived causally: ATR14, ATR_pct, EMA20, EMA50, trend_state.  
Region: inferred from ticker suffix (`.PA`/`.DE`/`.L` → EU/UK else US).

## Gaps remaining after adapter

- No intrabar path → same-bar stop+TP uses conservative gap/open rule
- Forward PAPER tagged arms start empty until future BUY journals are observed
- Linked PAPER profit_delta remains heuristic (separate certainty layer)
- `average_hold_time` available only on bar-replay trades, not fade snapshots

## Safety

Does not modify `live_bot.py`, `core/trailing.py`, or `portfolio.csv`.
