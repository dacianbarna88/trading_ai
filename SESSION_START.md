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
| 2 Selection | In progress: first run, 74 variants, none passes every gate yet |
| 3 Engine on broker paper API (Alpaca) | Not started; needs Dacian's Alpaca paper account and keys |
| 4 Paper for 3+ months | Not started |
| 5 Real money | Owner decision only; Claude never places real trades |

## Commands

```bash
pip install -r requirements.txt
python -m tae2 research --refresh      # download prices, validate, run every candidate
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
| `tests/` | Hermetic tests, incl. no-lookahead for every strategy |

## Rules

- Paper only. No broker keys in the repo; `.env` is gitignored.
- Commit only when the owner asks.
- Change a gate only before looking at results, never to let a strategy pass.
