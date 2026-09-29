"""Constants for the stock research lab. Reuses tae2's Gates contract unchanged."""

from __future__ import annotations

from tae2.config import COST_BPS, DATA_RULES, DATA_START, EVAL_START, SPLIT_DATE, Gates

CACHE = "data_cache/stock_prices.parquet"
CASH = "SHY"  # same cash proxy tae2 uses -- a real, tradable T-bill ETF, not a synthetic 0% series
# tae2.data.fetch() hard-codes tae2.config.CALENDAR_TICKER ("SPY") as the
# trading-calendar reference; SPY must stay in this universe for that to work.
BENCHMARK = "Equal-weight universe"  # the rigorous bar: beat holding the same stocks, not just SPY

# Same five gates as tae2 (15+ yr history, >=10bps costs, beat benchmark both
# halves, drawdown no worse, deflated Sharpe >=0.95) -- only the benchmark
# name changes, to the harder "did stock-picking beat just holding the
# universe" bar instead of "60/40" (that comparison is what caught the
# legacy bot's entry signal having no real edge).
GATES = Gates(benchmark=BENCHMARK)

__all__ = [
    "CACHE",
    "CASH",
    "BENCHMARK",
    "GATES",
    "COST_BPS",
    "DATA_RULES",
    "DATA_START",
    "EVAL_START",
    "SPLIT_DATE",
]
