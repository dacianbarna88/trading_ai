# TAE Exit Replay Coverage Audit

**Generated:** 2026-07-22T10:57:56+00:00  
**Source commit:** `f7ed09e`  
**Mode:** READ_ONLY | **Code modified:** false | **Commit:** none

## 1. Inventory (portfolio.csv FIFO lots)

| Metric | Count |
|--------|------:|
| TOTAL_POSITIONS (BUY lots) | 87 |
| OPEN | 11 |
| CLOSED | 76 |
| WINNERS (closed PnL>0) | 29 |
| LOSERS (closed PnL<0) | 42 |
| FLAT_CLOSED | 5 |
| FORCED_CLOSE | 0 |
| ACTIVE_PAPER (open) | 13 |
| ARCHIVED | directory present (not unitized here) |
| BUY rows / SELL rows | 87 / 76 |
| Unique tickers ever | 38 |

FORCED_CLOSE note: No SELL Reason matched FORCE/EOD/CLOSE ALL patterns; forced_end_of_replay is a simulator label, not a live sell reason

## 2. Why only 11?

**Primary cause:** `OPEN_ONLY_LOADER`

Function `tae_exit_strategy_bar_replay.load_open_positions` returns only residual **open** FIFO lots from `portfolio.csv`.

Current eligible tickers (11): ABBV, AIR.PA, DIA, HD, LLY, MRK, PG, PM, SIE.DE, SPY, ULVR.L

### Exclusion reasons (separate categories)

| Reason | Count |
|--------|------:|
| CLOSED_POSITION_NOT_SELECTED_BY_OPEN_ONLY_LOADER | 76 |

**Not caused by (for the selected 11):**
- OHLCV download failure (11/11 tickers_loaded, 0 failed)
- ATR14 warmup insufficiency at selection stage
- delisted tickers in the selected set
- missing entry timestamp/price on the 11

OHLCV for selected set: `tickers_loaded=11`, `tickers_failed=[]`

## 3. Coverage

| Ratio | Value |
|-------|------:|
| eligible / total BUY lots | 12.64% |
| eligible / closed lots | 14.47% |
| eligible / open lots | 100.00% |

**Below 80%?** YES (vs total and vs closed).

eligible/total=12.6% and eligible/closed=14.5% are both << 80% because eligibility is defined as currently OPEN residual lots only. Among open lots, coverage is 100%. The 76 closed lots were excluded by loader design, not by OHLCV failure.

## 4. Potential maximum

| Sample | Size |
|--------|-----:|
| current sample | 11 |
| potential if closed lots included | 87 |
| maximum realistic (all BUY lots) | 87 |
| paper open (separate book) | 13 |

### Classification

- **IMMEDIAT:** 0 — No additional positions enter without code/wiring change; OHLCV already works for open set
- **Necesită doar wiring:** 76 — Include closed FIFO lots in replay cohort (same portfolio.csv fields already present)
- **Necesită market history:** 76 — Closed lots also need post-entry bars; expected available via same download_history path that succeeded 11/11
- **Necesită mapping:** 76 — portfolio.csv rows lack canonical decision_id; synthetic PF- ids used today; paper trades have decision_id
- **Imposibil:** 0 — No lot identified as permanently irrecoverable from field inventory alone

## 5. Bias assessment

**Verdict: `BIASED`**

- Closed lot win rate: 38.2%
- Open unrealized positive rate: 27.3%
- Regions all buys: {'US': 59, 'UK': 13, 'EU': 15}
- Regions open sample: {'US': 8, 'EU': 2, 'UK': 1}
- Hold days median open vs closed: 5.85 vs 2.82
- Closed exit buckets: {'TAKE_PROFIT_OR_SIGNAL': 33, 'STOP_LOSS': 38, 'REDUCE_SIMULATION': 5}

Reasons:
- survivorship: sample is only currently open positions; closed losers/winners excluded by loader design
- calendar_skew: open entries span 2026-06-24→2026-07-22; closed span 2026-06-07→2026-07-20
- region_mix_open={'US': 8, 'EU': 2, 'UK': 1} vs all_buys={'US': 59, 'UK': 13, 'EU': 15}
- hold_time: open_median_days=5.8 vs closed_median_days=2.8

## 6. Missing data inventory (no solutions)

### CLOSED_POSITION_NOT_SELECTED_BY_OPEN_ONLY_LOADER (n=76)

Already present: ticker, entry_timestamp, entry_price, shares, exit_timestamp, exit_price, exit_reason

Missing for inclusion in *current* pipeline:
- selection_in_load_open_positions (code filter, not missing market data)
- canonical decision_id on live portfolio rows
- explicit exit_strategy_arm tag

### Paper book

- Included in exit bar-replay sample: **false**
- Reason: `EXIT_COMPARISON_USES_LIVE_PORTFOLIO_CSV_OPEN_ONLY_NOT_PAPER_BOOK`
- Paper-only open tickers: AAPL, MC.PA, SHEL.L

### Decision validation / replay

- Paper decisions / validation results: 25 / 25
- Included in bar-replay entry universe: **false** (separate linked_paper certainty layer; not used as bar-replay entry universe)

## 7. Minimum recommendation

**`SMALL_REPLAY_EXTENSION`**

Coverage is low because the adapter intentionally selects only currently open portfolio lots. Closed lots already have entry/exit fields in portfolio.csv. The minimal change is to extend the replay cohort builder to include closed FIFO lots (still READ_ONLY / SHADOW), without new subsystems.

## Safety

- Algorithms / strategies / live_bot / trailing / portfolio / replay code: **not modified**
- No commit (READ_ONLY audit artifacts only)
