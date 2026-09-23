# Session Start — TAE 2.0

**Read this first. It is the single entry point for the project.**

## What this is

An evidence-first ETF portfolio system. It answers one question: *which
portfolio should I hold this month, proven on 15+ years of history?* It does
not pick individual stocks and does not trade on hourly signals.

The legacy hourly paper bot (V1/V2/V3, ~137k lines) was retired on
2026-09-23: backtested 2010–2026 its entry signal returned 4%/yr against
20.6%/yr for simply holding the same stocks, and 82 of its last 239 commits
were fixes. It is preserved at git tag `legacy-bot-final`
(`git checkout legacy-bot-final`). The diagnosis and plan:
https://claude.ai/artifact/4rmxeAZzqAHfMPQivuugyA

## Principles

1. **Portfolio, not trades.** Strategies output target weights on a calendar
   (month-end); the engine brings the portfolio to them.
2. **Evidence before code.** Nothing runs on paper until it passes the gates
   in `tae2/config.py` on 15+ years of history with costs. Paper validates
   execution, not edge.
3. **One engine, one path.** The one-day decision→trade lag, costs and data
   validation live in the engine only; strategies can't skip them.
4. **Fail closed on data.** A missing, stale, gapped or partial bar stops the
   run (`tae2/data.py`), it is never replaced by an older value.
5. **The broker executes and keeps the books** (Alpaca paper, Phase 3). No
   home-made fills or accounting.
6. **Benchmark decides.** Every result is judged against 60/40 and SPY.
7. **Small.** A module stays only if removing it makes results worse.

## Status (2026-09-23)

| Phase | State |
|---|---|
| 0 Legacy bot stopped | Done: launchd job unloaded, code at tag `legacy-bot-final` |
| 1 Research lab | Done: data validation, backtester, strategies, gates, walk-forward, tests |
| 2 Selection | In progress: 94 variants; two pass every gate (see below) |
| 3 Engine on broker paper API (Alpaca) | Built (`tae2/engine.py`); waiting for Dacian's Alpaca paper keys to go live |
| 4 Paper for 3+ months | Not started |
| 5 Real money | Owner decision only; Claude never places real trades |

## Phase 2 result (2026-09-23, 94 variants, 10 bps costs, data to 2026-09-21)

| Strategy | CAGR | Sharpe | Max DD | Sharpe 2008–16 / 2017–26 | Robustness |
|---|---:|---:|---:|---|---|
| 60/40 (benchmark) | 8.3% | 0.78 | −31.4% | 0.63 / 0.93 | — |
| 60/40 core 50% + dual momentum 3m 50% | 9.1% | 0.89 | −20.0% | 0.75 / 1.02 | Fragile: only the 3-month lookback beats 60/40; 6/9/12 don't |
| 60/40 core 70% + GTAA 6m 30% | 7.2% | 0.81 | −23.7% | 0.65 / 0.97 | Robust on drawdown: all 8 variants cut max DD to −17..−25%; first-half Sharpe edge is thin |

Both still pass at 20 bps costs. Neither adds much return; the gain is smaller
crashes (2008: −5% vs −18% for the dual-momentum blend). Next: run both on
Alpaca paper next to 60/40 (phase 3–4).

## Paper engine (phase 3)

`python -m tae2 rebalance` computes the strategy's targets for the latest
*completed* month-end, with the same functions and validated prices as the
backtest, and plans orders for the Alpaca **paper** account. Without
`--submit` it only prints them (with no keys it plans for an empty $30k
book). With `--submit` it sells first, waits for fills, then buys with
dollar-sized orders, and records the decision in `state/engine.json` so it
never executes the same month twice. It stops before touching the broker on
bad data, a closed market, open orders from an earlier run, or a blocked
account. The paper URL is hard-wired; any other Alpaca URL is refused. The
engine owns the whole account: positions outside the targets are sold.

Going live on paper:
1. Create an Alpaca account, open the **Paper** dashboard, generate API keys.
2. `cp .env.example .env` and paste the two keys; pick `TAE2_STRATEGY`
   (`core_gtaa` is the default and the more robust candidate).
3. `python -m tae2 rebalance` (dry run against the real paper account).
4. Schedule it: `cp deploy/com.tae2.rebalance.plist ~/Library/LaunchAgents/`
   then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tae2.rebalance.plist`.
   It runs weekdays at 21:30 Bucharest time; logs go to `state/launchd.log`.

## Commands

```bash
pip install -r requirements.txt
python -m tae2 research --refresh      # download prices, validate, run every candidate
python -m tae2 rebalance              # show the orders the engine would place
python -m unittest discover -s tests -t .
```

`research` refuses to run when price validation fails; `--allow-data-issues`
runs anyway and lists the problems in the report. Reports go to `output/`,
prices to `data_cache/` (both gitignored).

## Layout

| Path | Role |
|---|---|
| `tae2/config.py` | Universe, costs, gates, parameter grids |
| `tae2/data.py` | Fetch, cache and validate daily prices |
| `tae2/backtest.py` | Target-weight engine: next-day execution, costs, drift |
| `tae2/strategies.py` | Strategies as pure functions (prices → weights) |
| `tae2/stats.py` | Metrics and the deflated Sharpe ratio |
| `tae2/gates.py` | Pass/fail gates |
| `tae2/research.py` | Walk-forward run and Markdown report |
| `tae2/engine.py` | Paper execution: targets → orders, once per decision |
| `tae2/rebalance.py` | Pure order planning (sells first, no leverage) |
| `tae2/broker.py` | Minimal Alpaca client, paper URL only |
| `deploy/` | Daily launchd job (install by hand, see above) |
| `tests/` | Hermetic tests, incl. no-lookahead for every strategy |

## Rules

- Paper only. No broker keys in the repo; `.env` is gitignored.
- Commit only when the owner asks.
- Change a gate only before looking at results, never to let a strategy pass.
