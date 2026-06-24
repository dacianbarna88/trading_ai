import pandas as pd

from config.settings import MIN_CASH_RESERVE, MIN_SCORE_TO_BUY
from core.market_regime import get_max_positions
from core.portfolio import get_cash_available, get_open_positions
from core.historical_risk import get_risk_multiplier
from core.forecast_risk import get_forecast_multiplier
from core.entry_filter import get_dynamic_min_score_to_buy
from core.allocation import get_allocation_weight


def get_dynamic_trade_size(signals_df, portfolio, market_regime):
    cash = get_cash_available(portfolio)
    investable_cash = max(cash - MIN_CASH_RESERVE, 0)
    positions = get_open_positions(portfolio)

    candidates = signals_df[
        (signals_df["Signal"] == "STRONG BUY")
        & (pd.to_numeric(signals_df["Score"], errors="coerce") >= get_dynamic_min_score_to_buy())
    ].copy()

    if market_regime == "BEAR":
        candidates = candidates.iloc[0:0]

    candidates = candidates[~candidates["Ticker"].isin(positions.keys())]

    available_slots = max(get_max_positions(market_regime) - len(positions), 0)

    if candidates.empty or available_slots <= 0 or investable_cash <= 0:
        return 0

    buy_count = min(len(candidates), available_slots)

    candidates = candidates.sort_values("Score", ascending=False).head(buy_count)
    weights = candidates["Score"].apply(get_allocation_weight)
    total_weight = weights.sum()

    if total_weight <= 0:
        return 0

    trade_size = investable_cash / total_weight
    trade_size *= get_risk_multiplier()
    trade_size *= get_forecast_multiplier()

    return round(trade_size, 2)


def get_score_adjusted_trade_size(base_trade_size, score):
    if score < get_dynamic_min_score_to_buy():
        return 0

    return round(base_trade_size * get_allocation_weight(score), 2)

