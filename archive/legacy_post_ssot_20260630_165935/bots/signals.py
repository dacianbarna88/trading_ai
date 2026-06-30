from datetime import datetime

import pandas as pd
import yfinance as yf

from config.settings import MIN_SCORE_TO_BUY, LIVE_SIGNALS_FILE, V41_SAFE_MODE
from core.indicators import calculate_rsi
from core.v41_shadow import run_v41_shadow
from data.alerts import save_alert
from data.storage import load_watchlist
from utils.logger import log


def generate_signals(manage_portfolio, update_portfolio_prices):
    results = []
    tickers = load_watchlist()

    log(f"Analizez {len(tickers)} tickere din watchlist.txt")

    for ticker in tickers:
        try:
            data = yf.download(
                ticker,
                period="6mo",
                auto_adjust=False,
                progress=False,
            )

            if data.empty:
                continue

            if len(data.columns.names) > 1:
                data.columns = data.columns.droplevel(1)

            data["SMA20"] = data["Close"].rolling(window=20).mean()
            data["SMA50"] = data["Close"].rolling(window=50).mean()
            data["RSI"] = calculate_rsi(data["Close"])
            data["AVG_VOLUME_20"] = data["Volume"].rolling(window=20).mean()
            data["HIGH_20"] = data["High"].rolling(window=20).max()

            last_close = float(data["Close"].iloc[-1])
            last_sma20 = float(data["SMA20"].iloc[-1])
            last_sma50 = float(data["SMA50"].iloc[-1])
            last_rsi = float(data["RSI"].iloc[-1])
            last_volume = float(data["Volume"].iloc[-1])
            avg_volume_20 = float(data["AVG_VOLUME_20"].iloc[-1])
            high_20 = float(data["HIGH_20"].iloc[-1])

            if pd.isna(last_sma20) or pd.isna(last_sma50) or pd.isna(last_rsi):
                continue

            score = 0

            # Trend de bază: prețul este peste media ultimelor 50 zile.
            if last_close > last_sma50:
                score += 40

            # RSI sănătos: suficient momentum, dar nu excesiv.
            if 40 < last_rsi < 65:
                score += 20

            # Zona preferată: momentum moderat, de obicei mai stabil.
            if 50 < last_rsi < 60:
                score += 10

            # Trend accelerat: media scurtă este peste media medie.
            if last_sma20 > last_sma50:
                score += 20

            # Confirmare prin volum: interes peste media ultimelor 20 zile.
            volume_confirmed = bool(
                not pd.isna(avg_volume_20)
                and avg_volume_20 > 0
                and last_volume > avg_volume_20
            )
            if volume_confirmed:
                score += 20

            # Breakout: prețul este aproape de maximul ultimelor 20 zile.
            breakout_20 = bool(
                not pd.isna(high_20)
                and high_20 > 0
                and last_close >= high_20 * 0.995
            )
            if breakout_20:
                score += 20

            if score >= MIN_SCORE_TO_BUY:
                signal = "STRONG BUY"
            elif last_rsi > 70:
                signal = "TAKE PROFIT"
            else:
                signal = "WAIT"

            row = {
                "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": ticker,
                "Price": round(last_close, 2),
                "SMA20": round(last_sma20, 2),
                "SMA50": round(last_sma50, 2),
                "RSI": round(last_rsi, 2),
                "Volume": int(last_volume),
                "Avg_Volume_20": int(avg_volume_20) if not pd.isna(avg_volume_20) else None,
                "Breakout_20": breakout_20,
                "Score": score,
                "Signal": signal,
            }

            results.append(row)

            if signal in ["STRONG BUY", "TAKE PROFIT"]:
                save_alert(row)

        except Exception as e:
            log(f"{ticker}: ERROR {e}")

    df = pd.DataFrame(results)

    if not df.empty:
        df = df.sort_values(by="Score", ascending=False)
        df.to_csv(LIVE_SIGNALS_FILE, index=False)

        log("live_signals.csv actualizat.")

        if V41_SAFE_MODE:
            run_v41_shadow(df)

        manage_portfolio(df)
        update_portfolio_prices()

