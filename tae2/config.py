"""TAE 2.0 settings: universe, costs and the validation gates.

Everything a research run depends on lives here, so a result can be traced
back to one set of numbers. Gates are fixed before looking at results.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# US-listed ETFs with daily history back to 2007 or earlier. ETFs have no
# survivorship bias: the funds that existed then are the ones tested now.
UNIVERSE: dict[str, str] = {
    "SPY": "US large caps (S&P 500)",
    "QQQ": "US tech-heavy large caps (Nasdaq 100)",
    "IWM": "US small caps (Russell 2000)",
    "EFA": "Developed markets ex-US",
    "EEM": "Emerging markets",
    "VNQ": "US real estate (REITs)",
    "DBC": "Broad commodities",
    "GLD": "Gold",
    "TLT": "US Treasuries 20+ years",
    "IEF": "US Treasuries 7-10 years",
    "LQD": "US investment-grade corporate bonds",
    "TIP": "US inflation-protected Treasuries",
    "SHY": "US Treasuries 1-3 years (cash proxy)",
}
CASH = "SHY"
CALENDAR_TICKER = "SPY"  # trading days = days SPY traded

DATA_START = "2006-01-01"
EVAL_START = "2008-01-01"  # first 12+ months only warm up lookbacks
SPLIT_DATE = "2017-01-01"  # in-sample / out-of-sample and the two "halves"

# Paid on every dollar of turnover (commission + spread + slippage).
COST_BPS = 10.0


@dataclass(frozen=True)
class Gates:
    """Pass criteria a strategy must meet before it may run on paper."""

    min_years: float = 15.0
    min_cost_bps: float = 10.0
    benchmark: str = "60/40"
    # Sharpe must beat the benchmark in both halves, not only overall.
    beat_benchmark_both_halves: bool = True
    # Max drawdown no worse than the benchmark's (drawdowns are negative).
    max_drawdown_vs_benchmark: bool = True
    # Probability the Sharpe is real after counting every variant tried.
    min_deflated_sharpe: float = 0.95


GATES = Gates()


@dataclass(frozen=True)
class DataRules:
    """Validation applied to every price series before it is used."""

    max_daily_move: float = 0.25  # |return| above this is flagged for review
    max_gap_days: int = 3  # consecutive calendar-trading days missing
    allowed_holiday_lag: int = 0  # business days a last bar may trail the expected session


DATA_RULES = DataRules()


@dataclass(frozen=True)
class ResearchPlan:
    """Parameter grids for the walk-forward search (every variant counts as a trial)."""

    sma_months: tuple[int, ...] = (6, 8, 10, 12)
    momentum_months: tuple[int, ...] = (3, 6, 9, 12)
    top_n: tuple[int, ...] = (2, 3, 4)
    vol_target: tuple[float, ...] = (0.06, 0.08, 0.10)
    core_weight: tuple[float, ...] = (0.5, 0.7)  # share kept in the 60/40 core (phase 2 blends)
    extra: dict[str, object] = field(default_factory=dict)


PLAN = ResearchPlan()
