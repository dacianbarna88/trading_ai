import pandas as pd

from config.settings import (
    MIN_SCORE_TO_BUY,
    V41_LOG_DISAGREEMENTS,
    V41_SHADOW_FILE,
)
from utils.logger import log
from v41_4_live_strategy import v41_live_decision


def run_v41_shadow(signals_df):

    rows = []

    if signals_df is None or signals_df.empty:
        pd.DataFrame(rows).to_csv(V41_SHADOW_FILE, index=False)
        return pd.DataFrame(rows)

    signals_df = signals_df[signals_df["Signal"].astype(str) == "STRONG BUY"]

    for _, row in signals_df.iterrows():

        ticker = row["Ticker"]
        price = float(row["Price"])
        sma = float(row["SMA50"])
        rsi = float(row["RSI"])

        res = v41_live_decision(ticker, price, sma, rsi)

        v4_buy = str(row.get("Signal")) == "STRONG BUY" and float(row.get("Score", 0)) >= MIN_SCORE_TO_BUY
        v41_buy = res["action"] == "BUY"

        rows.append({
            "Time": row.get("Time"),
            "Ticker": ticker,
            "V4_Signal": row.get("Signal"),
            "V4_Score": row.get("Score"),
            "V41_Fusion": res["fusion"],
            "V41_Action": res["action"],
            "Would_V4_Buy": v4_buy,
            "Would_V41_Buy": v41_buy,
            "Status": "PAPER_ONLY",
            "Execution": "NO_BROKER | NO_AUTO_EXECUTION"
        })

        if V41_LOG_DISAGREEMENTS and v4_buy != v41_buy:
            log(f"V41 SHADOW mismatch {ticker}: V4={row.get('Signal')} score={row.get('Score')} V41={res['action']} fusion={res['fusion']}")

    out = pd.DataFrame(rows)
    out.to_csv(V41_SHADOW_FILE, index=False)
    log(f"V41 shadow signals saved: {V41_SHADOW_FILE} ({len(out)} rows)")

    return out
