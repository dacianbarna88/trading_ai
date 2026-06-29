import os
import time
from datetime import datetime, time as dtime
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf


STARTING_CAPITAL = 30000
INTERVAL_SECONDS = 60

MIN_SCORE_TO_BUY = 80
TAKE_PROFIT_PCT = 5
STOP_LOSS_PCT = -3
MAX_POSITIONS = 12
MIN_TRADE_USD = 250
MAX_TRADE_USD = 2500

MARKET_REGIME_FILTER = True
MARKET_REGIME_TICKER = "SPY"
MARKET_REGIME_SMA = 200

TEST_SELL_MODE = False
ALLOW_BUY_WHEN_MARKET_CLOSED = False

WATCHLIST_FILE = "watchlist.txt"
LIVE_SIGNALS_FILE = "live_signals.csv"
PORTFOLIO_FILE = "portfolio.csv"
ALERTS_FILE = "alerts_log.csv"
LOG_FILE = "bot_output.log"
STATUS_FILE = "bot_status.txt"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def log(message):
    text = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    print(text)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def set_status(status):
    Path(STATUS_FILE).write_text(status, encoding="utf-8")


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=10,
        )

        if response.status_code != 200:
            log(f"Telegram error response: {response.text}")
            return False

        return True

    except Exception as e:
        log(f"Telegram error: {e}")
        return False


def is_market_open():
    from markets.market_hours import any_market_open, get_market_statuses, get_open_markets

    statuses = get_market_statuses()
    open_markets = get_open_markets()
    closed_markets = [name for name, is_open in statuses.items() if not is_open]
    log(
        "Market sessions OPEN=[{open}] CLOSED=[{closed}]".format(
            open=",".join(open_markets) if open_markets else "NONE",
            closed=",".join(closed_markets) if closed_markets else "NONE",
        )
    )
    return any_market_open()


def get_ticker_market(ticker):
    from markets.market_hours import get_ticker_market as resolve_market

    return resolve_market(ticker)


def is_ticker_market_open(ticker):
    from markets.market_hours import is_ticker_market_open as ticker_open

    return ticker_open(ticker)


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

        if last_close > last_sma:
            log(
                f"Market Regime: BULL | "
                f"{MARKET_REGIME_TICKER} {last_close:.2f} > SMA{MARKET_REGIME_SMA} {last_sma:.2f}"
            )
            return "BULL"

        log(
            f"Market Regime: BEAR | "
            f"{MARKET_REGIME_TICKER} {last_close:.2f} < SMA{MARKET_REGIME_SMA} {last_sma:.2f}"
        )
        return "BEAR"

    except Exception as e:
        log(f"Market Regime error: {e}. Permit BUY.")
        return "UNKNOWN"


def load_watchlist():
    path = Path(WATCHLIST_FILE)

    if path.exists():
        tickers = [
            line.strip().upper()
            for line in path.read_text().splitlines()
            if line.strip()
        ]

        if tickers:
            return tickers

    return ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]


def calculate_rsi(close, period=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def get_latest_price(ticker):
    try:
        data = yf.download(
            ticker,
            period="5d",
            auto_adjust=False,
            progress=False,
        )

        if data.empty:
            return None

        if len(data.columns.names) > 1:
            data.columns = data.columns.droplevel(1)

        return float(data["Close"].iloc[-1])

    except Exception as e:
        log(f"Eroare preț live {ticker}: {e}")
        return None


def load_csv_safe(file, columns):
    path = Path(file)

    if path.exists():
        try:
            df = pd.read_csv(path)
        except Exception:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()

    for col in columns:
        if col not in df.columns:
            df[col] = None

    return df[columns]


def load_portfolio():
    columns = [
        "Date",
        "Ticker",
        "Action",
        "Price",
        "Shares",
        "Score",
        "Signal",
        "Reason",
        "Current_Price",
        "Invested",
        "Current_Value",
        "PnL",
        "PnL_%",
    ]

    return load_csv_safe(PORTFOLIO_FILE, columns)


def save_portfolio(df):
    df.to_csv(PORTFOLIO_FILE, index=False)


def update_portfolio_prices():
    portfolio = load_portfolio()

    if portfolio.empty:
        return

    portfolio["Price"] = pd.to_numeric(portfolio["Price"], errors="coerce")
    portfolio["Shares"] = pd.to_numeric(portfolio["Shares"], errors="coerce")

    for i, row in portfolio.iterrows():
        ticker = row["Ticker"]

        if pd.isna(ticker):
            continue

        current_price = get_latest_price(ticker)

        if current_price is None:
            current_price = row["Price"]

        price = float(row["Price"])
        shares = float(row["Shares"])

        invested = price * shares
        current_value = float(current_price) * shares
        pnl = current_value - invested
        pnl_pct = (pnl / invested) * 100 if invested else 0

        portfolio.loc[i, "Current_Price"] = round(current_price, 2)
        portfolio.loc[i, "Invested"] = round(invested, 4)
        portfolio.loc[i, "Current_Value"] = round(current_value, 4)
        portfolio.loc[i, "PnL"] = round(pnl, 4)
        portfolio.loc[i, "PnL_%"] = round(pnl_pct, 4)

    save_portfolio(portfolio)
    log("portfolio.csv actualizat cu prețuri live.")


def get_open_positions(portfolio):
    positions = {}

    if portfolio.empty:
        return positions

    portfolio["Price"] = pd.to_numeric(portfolio["Price"], errors="coerce")
    portfolio["Shares"] = pd.to_numeric(portfolio["Shares"], errors="coerce")

    for ticker in portfolio["Ticker"].dropna().unique():
        rows = portfolio[portfolio["Ticker"] == ticker]

        buys = rows[rows["Action"].astype(str).str.upper() == "BUY"]
        sells = rows[rows["Action"].astype(str).str.upper() == "SELL"]

        buy_shares = buys["Shares"].sum()
        sell_shares = sells["Shares"].sum()
        open_shares = buy_shares - sell_shares

        if open_shares > 0:
            buy_value = (buys["Price"] * buys["Shares"]).sum()
            avg_price = buy_value / buy_shares if buy_shares else 0

            positions[ticker] = {
                "shares": open_shares,
                "avg_price": avg_price,
            }

    return positions


def get_cash_available(portfolio):
    if portfolio.empty:
        return STARTING_CAPITAL

    portfolio["Price"] = pd.to_numeric(portfolio["Price"], errors="coerce")
    portfolio["Shares"] = pd.to_numeric(portfolio["Shares"], errors="coerce")

    buys = portfolio[portfolio["Action"].astype(str).str.upper() == "BUY"]
    sells = portfolio[portfolio["Action"].astype(str).str.upper() == "SELL"]

    spent = (buys["Price"] * buys["Shares"]).sum()
    received = (sells["Price"] * sells["Shares"]).sum()

    return STARTING_CAPITAL - spent + received


def save_alert(row):
    columns = ["Time", "Ticker", "Price", "SMA50", "RSI", "Score", "Signal"]

    alerts = load_csv_safe(ALERTS_FILE, columns)
    alerts = pd.concat([alerts, pd.DataFrame([row])], ignore_index=True)
    alerts.to_csv(ALERTS_FILE, index=False)


def get_dynamic_trade_size(signals_df, portfolio, market_regime):
    cash = get_cash_available(portfolio)
    positions = get_open_positions(portfolio)

    candidates = signals_df[
        (signals_df["Signal"] == "STRONG BUY")
        & (pd.to_numeric(signals_df["Score"], errors="coerce") >= MIN_SCORE_TO_BUY)
    ].copy()

    if market_regime == "BEAR":
        candidates = candidates.iloc[0:0]

    candidates = candidates[~candidates["Ticker"].isin(positions.keys())]

    available_slots = max(MAX_POSITIONS - len(positions), 0)

    if candidates.empty or available_slots <= 0 or cash <= 0:
        return 0

    buy_count = min(len(candidates), available_slots)

    return round(cash / buy_count, 2)


def buy_position(row, portfolio, trade_usd):
    ticker = row["Ticker"]
    price = float(row["Price"])
    cash = get_cash_available(portfolio)

    if trade_usd <= 0:
        return portfolio

    if trade_usd < MIN_TRADE_USD:
        log(f"BUY blocat pentru {ticker}: trade_usd ${trade_usd:.2f} sub MIN_TRADE_USD ${MIN_TRADE_USD:.2f}")
        return portfolio

    if trade_usd > MAX_TRADE_USD:
        trade_usd = MAX_TRADE_USD

    if cash < trade_usd:
        trade_usd = cash

    shares = round(trade_usd / price, 4)
    invested = round(price * shares, 4)

    new_trade = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Ticker": ticker,
        "Action": "BUY",
        "Price": round(price, 2),
        "Shares": shares,
        "Score": int(row["Score"]),
        "Signal": row["Signal"],
        "Reason": "AUTO STRONG BUY DYNAMIC + MARKET REGIME",
        "Current_Price": round(price, 2),
        "Invested": invested,
        "Current_Value": invested,
        "PnL": 0,
        "PnL_%": 0,
    }

    portfolio = pd.concat([portfolio, pd.DataFrame([new_trade])], ignore_index=True)

    log(f"BUY executat: {ticker} | ${trade_usd:.2f} | {shares} shares @ {price:.2f}")

    send_telegram(
        f"🚀 AUTO BUY\n\n"
        f"Ticker: {ticker}\n"
        f"Price: {price:.2f}\n"
        f"Shares: {shares}\n"
        f"Invested: ${invested:.2f}\n"
        f"Score: {row['Score']}\n"
        f"RSI: {row['RSI']}"
    )

    return portfolio


def sell_position(row, portfolio, reason):
    ticker = row["Ticker"]
    price = float(row["Price"])

    positions = get_open_positions(portfolio)

    if ticker not in positions:
        return portfolio

    shares = round(positions[ticker]["shares"], 4)
    avg_price = float(positions[ticker]["avg_price"])

    invested = avg_price * shares
    current_value = price * shares
    pnl = current_value - invested
    pnl_pct = (pnl / invested) * 100 if invested else 0

    new_trade = {
        "Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Ticker": ticker,
        "Action": "SELL",
        "Price": round(price, 2),
        "Shares": shares,
        "Score": int(row["Score"]),
        "Signal": row["Signal"],
        "Reason": reason,
        "Current_Price": round(price, 2),
        "Invested": round(invested, 4),
        "Current_Value": round(current_value, 4),
        "PnL": round(pnl, 4),
        "PnL_%": round(pnl_pct, 4),
    }

    portfolio = pd.concat([portfolio, pd.DataFrame([new_trade])], ignore_index=True)

    log(f"SELL executat: {ticker} | {shares} shares @ {price:.2f} | {reason}")

    send_telegram(
        f"💰 AUTO SELL\n\n"
        f"Ticker: {ticker}\n"
        f"Price: {price:.2f}\n"
        f"Shares: {shares}\n"
        f"PnL: ${pnl:.2f}\n"
        f"PnL %: {pnl_pct:.2f}%\n"
        f"Reason: {reason}"
    )

    return portfolio


def manage_portfolio(signals_df, advisory_state=None):
    portfolio = load_portfolio()
    positions = get_open_positions(portfolio)

    if advisory_state is None:
        from research_core.governance.live_advisory_runtime import load_live_advisory

        advisory_state = load_live_advisory()

    from research_core.governance.live_advisory_runtime import (
        advisory_runtime_summary,
        get_advisory_action,
        should_block_new_buy,
    )

    tae_action = get_advisory_action(advisory_state)
    block_new_buy, tae_block_reason = should_block_new_buy(advisory_state)
    log(f"TAE Live Advisory: {advisory_runtime_summary(advisory_state)}")
    if advisory_state.warning:
        log(f"TAE Live Advisory warning: {advisory_state.warning}")

    if tae_action == "BUY_ADVISORY":
        log("TAE advisory supportive (BUY_ADVISORY — no automatic buy)")
    elif tae_action == "SELL_ADVISORY":
        log("TAE SELL_ADVISORY — informational only; existing SELL rules unchanged")

    market_regime = get_market_regime()
    trade_size = get_dynamic_trade_size(signals_df, portfolio, market_regime)

    log(f"Market Regime activ: {market_regime}")
    is_market_open()

    for _, row in signals_df.iterrows():
        ticker = row["Ticker"]
        signal = row["Signal"]
        score = pd.to_numeric(row["Score"], errors="coerce")
        price = pd.to_numeric(row["Price"], errors="coerce")

        if pd.isna(price) or price <= 0:
            continue

        if ticker not in positions:
            ticker_market = get_ticker_market(ticker)
            ticker_session_open = is_ticker_market_open(ticker)

            if ticker_session_open or ALLOW_BUY_WHEN_MARKET_CLOSED:
                if (
                    signal == "STRONG BUY"
                    and score >= MIN_SCORE_TO_BUY
                    and market_regime == "BULL"
                ):
                    if block_new_buy:
                        log(
                            f"BUY blocat pentru {ticker}: {tae_block_reason}"
                        )
                    elif len(positions) < MAX_POSITIONS:
                        if tae_action == "BUY_ADVISORY":
                            log(f"TAE advisory supportive pentru {ticker}")
                        log(
                            f"BUY permis pentru {ticker}: piața {ticker_market} deschisă, "
                            f"signal={signal}, score={score}"
                        )
                        portfolio = buy_position(row, portfolio, trade_size)
                        positions = get_open_positions(portfolio)
                    elif len(positions) >= MAX_POSITIONS:
                        log(f"BUY blocat pentru {ticker}: MAX_POSITIONS ({MAX_POSITIONS})")

                elif signal == "STRONG BUY" and market_regime != "BULL":
                    log(f"BUY blocat pentru {ticker}: Market Regime {market_regime}")

            elif signal == "STRONG BUY":
                log(
                    f"BUY blocat pentru {ticker}: piața {ticker_market} închisă "
                    f"(US/EU/UK evaluate separat)"
                )

        else:
            avg_price = positions[ticker]["avg_price"]
            pnl_pct = ((price - avg_price) / avg_price) * 100

            if TEST_SELL_MODE:
                portfolio = sell_position(row, portfolio, "TEST SELL MODE")
                positions = get_open_positions(portfolio)

            elif signal == "TAKE PROFIT":
                portfolio = sell_position(row, portfolio, "TAKE PROFIT SIGNAL")
                positions = get_open_positions(portfolio)

            elif pnl_pct >= TAKE_PROFIT_PCT:
                portfolio = sell_position(row, portfolio, f"PROFIT +{pnl_pct:.2f}%")
                positions = get_open_positions(portfolio)

            elif pnl_pct <= STOP_LOSS_PCT:
                portfolio = sell_position(row, portfolio, f"STOP LOSS {pnl_pct:.2f}%")
                positions = get_open_positions(portfolio)

    save_portfolio(portfolio)

def generate_signals():
    from research_core.governance.live_advisory_runtime import load_live_advisory

    advisory_state = load_live_advisory()

    results = []
    tickers = load_watchlist()

    portfolio_for_risk = load_portfolio()
    open_positions_for_risk = get_open_positions(portfolio_for_risk)

    for open_ticker in open_positions_for_risk.keys():
        if open_ticker not in tickers:
            tickers.append(open_ticker)
            log(f"Risk Guard: adăugat {open_ticker} în ciclul curent pentru verificare SELL")

    log(f"Analizez {len(tickers)} tickere din watchlist.txt + poziții deschise")

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

            data["SMA50"] = data["Close"].rolling(window=50).mean()
            data["RSI"] = calculate_rsi(data["Close"])

            last_close = float(data["Close"].iloc[-1])
            last_sma = float(data["SMA50"].iloc[-1])
            last_rsi = float(data["RSI"].iloc[-1])

            score = 0

            if last_close > last_sma:
                score += 40

            if 40 < last_rsi < 65:
                score += 40

            if 50 < last_rsi < 60:
                score += 20

            if score >= 80:
                signal = "STRONG BUY"
            elif last_rsi > 70:
                signal = "TAKE PROFIT"
            else:
                signal = "WAIT"

            row = {
                "Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Ticker": ticker,
                "Price": round(last_close, 2),
                "SMA50": round(last_sma, 2),
                "RSI": round(last_rsi, 2),
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
        manage_portfolio(df, advisory_state=advisory_state)
        update_portfolio_prices()

        try:
            import subprocess
            subprocess.run(
                ["python3", "position_intelligence.py"],
                check=False
            )
            log("Position Intelligence actualizat automat.")
        except Exception as e:
            log(f"Eroare Position Intelligence auto-refresh: {e}")


if __name__ == "__main__":
    set_status("RUNNING")
    log("Live bot pornit.")
    is_market_open()

    send_telegram(
        "🟢 Trading AI Bot pornit.\n"
        "Status: RUNNING\n"
        "Telegram: ACTIV\n"
        "Market Regime Filter: ACTIV\n"
        f"Max poziții: {MAX_POSITIONS}"
    )

    try:
        while True:
            generate_signals()
            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        set_status("STOPPED")
        log("Live bot oprit manual.")
        send_telegram("🔴 Trading AI Bot oprit manual.")
