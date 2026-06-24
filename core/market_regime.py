import pandas as pd
import yfinance as yf

from config.settings import (
    MARKET_REGIME_FILTER,
    MARKET_REGIME_TICKER,
    MARKET_REGIME_SMA,
    MAX_POSITIONS_BULL,
    MAX_POSITIONS_NEUTRAL,
    MAX_POSITIONS_BEAR,
)
from utils.logger import log
from core.historical_risk import get_position_limit_multiplier


def get_market_regime():
    if not MARKET_REGIME_FILTER:
        return "BULL"

    try:
        data = yf.download(
            MARKET_REGIME_TICKER,
            period="2y",
            auto_adjust=False,
            progress=False,
        )

        if data.empty:
            log("Market Regime: nu am date. Permit BUY.")
            return "UNKNOWN"

        if len(data.columns.names) > 1:
            data.columns = data.columns.droplevel(1)

        sma = data["Close"].rolling(MARKET_REGIME_SMA).mean()

        last_close = float(data["Close"].iloc[-1])
        last_sma = float(sma.iloc[-1])

        if pd.isna(last_sma):
            log("Market Regime: SMA indisponibil. Permit BUY.")
            return "UNKNOWN"

        if last_close > last_sma * 1.02:
            return "BULL"

        if last_close < last_sma * 0.98:
            return "BEAR"

        return "NEUTRAL"

    except Exception as e:
        log(f"Market Regime error: {e}. Permit BUY.")
        return "UNKNOWN"


def get_max_positions(regime):
    if regime == "BULL":
        base_positions = MAX_POSITIONS_BULL
    elif regime == "NEUTRAL":
        base_positions = MAX_POSITIONS_NEUTRAL
    else:
        base_positions = MAX_POSITIONS_BEAR

    adjusted_positions = int(base_positions * get_position_limit_multiplier())

    return max(adjusted_positions, 0)
