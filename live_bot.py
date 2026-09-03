import os
import time
import traceback
from datetime import datetime, time as dtime

import pandas as pd
import yfinance as yf

from core.allocation import get_allocation_weight
from core.forecast_risk import get_forecast_multiplier
from core.historical_risk import get_risk_multiplier
from core.indicators import calculate_rsi, get_latest_price
from core.portfolio import get_cash_available, get_open_positions, open_buy_row_mask
from core.status import set_status
from data.storage import load_csv_safe, load_portfolio, load_watchlist, save_portfolio
from core.v51_policy_shadow import run_v51_policy_shadow
from markets.market_hours import get_ticker_market, is_ticker_market_open
from utils.logger import log
from utils.telegram import send_telegram


STARTING_CAPITAL = 30000
INTERVAL_SECONDS = 60

MIN_SCORE_TO_BUY = 90
TAKE_PROFIT_PCT = 5
STOP_LOSS_PCT = -3
MAX_POSITIONS = 12
MIN_TRADE_USD = 250
MAX_TRADE_USD = 2500
MIN_CASH_RESERVE = 500

MARKET_REGIME_FILTER = True
MARKET_REGIME_TICKER = "SPY"
MARKET_REGIME_SMA = 200

TEST_SELL_MODE = False
ALLOW_BUY_WHEN_MARKET_CLOSED = False
GLOBAL_MARKET_GATE_ENABLED = False

# Observation-only: logs where live_bot_v5_1.py's dynamic policy (regime,
# MAX_POSITIONS, entry threshold, trailing-stop) would have decided
# differently, without ever blocking a BUY or forcing a SELL here. Building
# an evidence base before any decision to migrate this bot's policy.
V51_POLICY_SHADOW_MODE = True

ALERTS_FILE = "alerts_log.csv"


def log_market_session_summary():
    """Log per-market session status. Does not gate BUY globally."""
    from markets.market_hours import get_market_statuses, get_open_markets

    statuses = get_market_statuses()
    open_markets = get_open_markets()
    closed_markets = [name for name, is_open in statuses.items() if not is_open]
    log(
        "Market sessions OPEN=[{open}] CLOSED=[{closed}]".format(
            open=",".join(open_markets) if open_markets else "NONE",
            closed=",".join(closed_markets) if closed_markets else "NONE",
        )
    )
    if not GLOBAL_MARKET_GATE_ENABLED:
        log("Global market gate disabled; evaluating BUY per ticker session.")


def is_market_open():
    """Backward-compatible alias — session log only, no global BUY gate."""
    log_market_session_summary()
    return True


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


def update_portfolio_prices():
    portfolio = load_portfolio()

    if portfolio.empty:
        return

    portfolio["Price"] = pd.to_numeric(portfolio["Price"], errors="coerce")
    portfolio["Shares"] = pd.to_numeric(portfolio["Shares"], errors="coerce")

    # A ticker-only "is this ticker open" check is not enough: a
    # closed-then-reopened ticker has both a stale closed BUY row and a
    # fresh open BUY row sharing the same ticker name. Only rows after that
    # ticker's most recent SELL are the open position.
    open_rows = open_buy_row_mask(portfolio)

    for i, row in portfolio.iterrows():
        ticker = row["Ticker"]
        action = str(row.get("Action", "")).upper()

        if pd.isna(ticker):
            continue

        # Realized rows and capital flows must keep PnL frozen at execution time.
        if action in {"SELL", "DEPOSIT"}:
            continue

        if str(ticker).upper() == "CASH":
            continue

        # Closed positions: do not rewrite historical BUY marks.
        if action == "BUY" and not open_rows.loc[i]:
            continue

        current_price = get_latest_price(ticker, log)

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
    log("portfolio.csv actualizat cu prețuri live (open BUY rows only).")


def save_alert(row):
    # live_bot.py's own scoring doesn't compute SMA20/Volume/Avg_Volume_20/
    # Breakout_20 (data/alerts.py's richer save_alert(), used via
    # research/signals.py, does), but load_csv_safe() projects the loaded
    # frame down to exactly this column list before writing it back to the
    # same shared alerts_log.csv — omitting those columns here would
    # silently erase them if the other writer had already populated them.
    columns = [
        "Time",
        "Ticker",
        "Price",
        "SMA20",
        "SMA50",
        "RSI",
        "Volume",
        "Avg_Volume_20",
        "Breakout_20",
        "Score",
        "Signal",
    ]

    alerts = load_csv_safe(ALERTS_FILE, columns)
    alerts = pd.concat([alerts, pd.DataFrame([row])], ignore_index=True)
    tmp_path = f"{ALERTS_FILE}.tmp"
    alerts.to_csv(tmp_path, index=False)
    os.replace(tmp_path, ALERTS_FILE)


def get_dynamic_trade_size(signals_df, portfolio, market_regime):
    cash = get_cash_available(portfolio)
    investable_cash = max(cash - MIN_CASH_RESERVE, 0)
    positions = get_open_positions(portfolio)

    candidates = signals_df[
        (signals_df["Signal"] == "STRONG BUY")
        & (pd.to_numeric(signals_df["Score"], errors="coerce") >= MIN_SCORE_TO_BUY)
    ].copy()

    if market_regime == "BEAR":
        candidates = candidates.iloc[0:0]

    candidates = candidates[~candidates["Ticker"].isin(positions.keys())]

    available_slots = max(MAX_POSITIONS - len(positions), 0)

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
    if score < MIN_SCORE_TO_BUY:
        return 0

    return round(base_trade_size * get_allocation_weight(score), 2)


def buy_position(row, portfolio, trade_usd):
    ticker = row["Ticker"]
    price = float(row["Price"])
    cash = get_cash_available(portfolio)
    investable_cash = max(cash - MIN_CASH_RESERVE, 0)

    if trade_usd <= 0:
        return portfolio

    if trade_usd < MIN_TRADE_USD:
        log(f"BUY blocat pentru {ticker}: trade_usd ${trade_usd:.2f} sub MIN_TRADE_USD ${MIN_TRADE_USD:.2f}")
        return portfolio

    if trade_usd > MAX_TRADE_USD:
        trade_usd = MAX_TRADE_USD

    if investable_cash <= 0:
        log(f"BUY blocat pentru {ticker}: cash reserve ${MIN_CASH_RESERVE:.2f} păstrat.")
        return portfolio

    if investable_cash < trade_usd:
        trade_usd = investable_cash

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


def manage_portfolio(signals_df, advisory_state=None, live_bot_cycle_id=None):
    portfolio = load_portfolio()
    positions = get_open_positions(portfolio)

    if live_bot_cycle_id is None:
        live_bot_cycle_id = datetime.now().strftime("%Y%m%d%H%M%S")

    if advisory_state is None:
        from research_core.governance.live_advisory_runtime import load_live_advisory

        advisory_state = load_live_advisory()

    from research_core.governance.live_advisory_runtime import (
        advisory_runtime_summary,
        get_advisory_action,
        should_block_new_buy,
    )
    from research_core.governance.shadow_validation_ledger import (
        log_buy_allowed,
        log_buy_blocked_by_tae,
        log_buy_skipped_other_reason,
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
    log_market_session_summary()

    exit_checked_tickers = set()

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
                        log_buy_blocked_by_tae(
                            ticker=ticker,
                            signal=signal,
                            score=score,
                            price=price,
                            advisory_state=advisory_state,
                            block_reason=tae_block_reason,
                            live_bot_cycle_id=live_bot_cycle_id,
                            warn_fn=log,
                        )
                    elif len(positions) < MAX_POSITIONS:
                        if tae_action == "BUY_ADVISORY":
                            log(f"TAE advisory supportive pentru {ticker}")
                        log(
                            f"BUY permis pentru {ticker}: piața {ticker_market} deschisă, "
                            f"signal={signal}, score={score}"
                        )
                        ticker_trade_size = get_score_adjusted_trade_size(trade_size, score)
                        est_shares = (
                            round(float(ticker_trade_size) / float(price), 4)
                            if ticker_trade_size and price > 0
                            else None
                        )
                        log_buy_allowed(
                            ticker=ticker,
                            signal=signal,
                            score=score,
                            price=price,
                            intended_trade_usd=ticker_trade_size,
                            shares=est_shares,
                            advisory_state=advisory_state,
                            block_new_buy=block_new_buy,
                            live_bot_cycle_id=live_bot_cycle_id,
                            warn_fn=log,
                        )
                        portfolio = buy_position(row, portfolio, ticker_trade_size)
                        positions = get_open_positions(portfolio)
                        # A ticker just bought this cycle needs no fallback
                        # exit check below: its avg_price is the price we
                        # just paid, so PnL is ~0% and the fallback pass
                        # would only waste an extra price fetch (or, in a
                        # razor-thin edge case, risk an immediate re-sell
                        # off a fresh quote fetched moments later).
                        exit_checked_tickers.add(ticker)
                    elif len(positions) >= MAX_POSITIONS:
                        skip_reason = f"MAX_POSITIONS ({MAX_POSITIONS})"
                        log(f"BUY blocat pentru {ticker}: {skip_reason}")
                        log_buy_skipped_other_reason(
                            ticker=ticker,
                            signal=signal,
                            score=score,
                            price=price,
                            block_reason=skip_reason,
                            advisory_state=advisory_state,
                            block_new_buy=block_new_buy,
                            live_bot_cycle_id=live_bot_cycle_id,
                            warn_fn=log,
                        )

                elif signal == "STRONG BUY" and market_regime != "BULL":
                    skip_reason = f"Market Regime {market_regime}"
                    log(f"BUY blocat pentru {ticker}: {skip_reason}")
                    log_buy_skipped_other_reason(
                        ticker=ticker,
                        signal=signal,
                        score=score,
                        price=price,
                        block_reason=skip_reason,
                        advisory_state=advisory_state,
                        block_new_buy=block_new_buy,
                        live_bot_cycle_id=live_bot_cycle_id,
                        warn_fn=log,
                    )

            elif signal == "STRONG BUY":
                skip_reason = "MARKET_SESSION_FILTER"
                log(f"BUY skipped for {ticker}: ticker market closed")
                log_buy_skipped_other_reason(
                    ticker=ticker,
                    signal=signal,
                    score=score,
                    price=price,
                    block_reason=skip_reason,
                    advisory_state=advisory_state,
                    block_new_buy=block_new_buy,
                    live_bot_cycle_id=live_bot_cycle_id,
                    warn_fn=log,
                )

        else:
            exit_checked_tickers.add(ticker)
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

    # Safety net: a held position whose ticker failed to produce a row this
    # cycle (a transient yfinance download error, or every download failing
    # so signals_df came back empty) would otherwise silently skip its
    # STOP_LOSS/TAKE_PROFIT check for the whole cycle. Fetch a fresh price
    # directly for any such ticker so the exit check still runs.
    for ticker in list(positions.keys()):
        if ticker in exit_checked_tickers:
            continue

        fallback_price = get_latest_price(ticker, log)
        if fallback_price is None or fallback_price <= 0:
            log(f"Exit check sărit pentru {ticker}: preț indisponibil în acest ciclu.")
            continue

        avg_price = positions[ticker]["avg_price"]
        pnl_pct = ((fallback_price - avg_price) / avg_price) * 100
        fallback_row = {"Ticker": ticker, "Price": fallback_price, "Score": 0, "Signal": "WAIT"}

        log(
            f"Exit check fallback pentru {ticker} (lipsă din signals_df): "
            f"preț {fallback_price:.2f} | PnL {pnl_pct:.2f}%"
        )

        if TEST_SELL_MODE:
            portfolio = sell_position(fallback_row, portfolio, "TEST SELL MODE")
            positions = get_open_positions(portfolio)

        elif pnl_pct >= TAKE_PROFIT_PCT:
            portfolio = sell_position(fallback_row, portfolio, f"PROFIT +{pnl_pct:.2f}% (fallback)")
            positions = get_open_positions(portfolio)

        elif pnl_pct <= STOP_LOSS_PCT:
            portfolio = sell_position(fallback_row, portfolio, f"STOP LOSS {pnl_pct:.2f}% (fallback)")
            positions = get_open_positions(portfolio)

    save_portfolio(portfolio)

    if V51_POLICY_SHADOW_MODE:
        run_v51_policy_shadow(
            signals_df,
            positions,
            live_regime=market_regime,
            live_max_positions=MAX_POSITIONS,
            live_min_score_to_buy=MIN_SCORE_TO_BUY,
            live_take_profit_pct=TAKE_PROFIT_PCT,
            live_stop_loss_pct=STOP_LOSS_PCT,
            live_bot_cycle_id=live_bot_cycle_id,
            warn_fn=log,
        )


def generate_signals():
    from research_core.governance.live_advisory_runtime import load_live_advisory

    advisory_state = load_live_advisory()
    live_bot_cycle_id = datetime.now().strftime("%Y%m%d%H%M%S")

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
        tmp_path = f"{LIVE_SIGNALS_FILE}.tmp"
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, LIVE_SIGNALS_FILE)

        log("live_signals.csv actualizat.")
    else:
        log(
            "Niciun semnal generat în acest ciclu (toate descărcările au eșuat) — "
            "verific poziții deschise pentru STOP_LOSS/TAKE_PROFIT oricum."
        )

    # These must run every cycle, not only when signals_df is non-empty:
    # if every ticker's download failed (e.g. a yfinance outage), skipping
    # them would silently skip STOP_LOSS/TAKE_PROFIT checks on already-held
    # positions for the whole cycle. manage_portfolio() itself also has a
    # per-ticker fallback for a partial failure (see exit_checked_tickers).
    manage_portfolio(
        df,
        advisory_state=advisory_state,
        live_bot_cycle_id=live_bot_cycle_id,
    )
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
    log_market_session_summary()

    send_telegram(
        "🟢 Trading AI Bot pornit.\n"
        "Status: RUNNING\n"
        "Telegram: ACTIV\n"
        "Market Regime Filter: ACTIV\n"
        f"Max poziții: {MAX_POSITIONS}"
    )

    try:
        while True:
            # An unhandled exception anywhere inside a cycle (network
            # error, unexpected data, a bug) must not silently kill the
            # whole process: that would permanently stop STOP_LOSS/
            # TAKE_PROFIT checks on live positions until a human notices
            # and restarts the bot. Log it, alert, and keep looping.
            try:
                generate_signals()
            except Exception as e:
                log(f"CICLU EROARE NEAȘTEPTATĂ: {e}\n{traceback.format_exc()}")
                send_telegram(f"⚠️ Bot cycle error (continuing): {e}")

            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        set_status("STOPPED")
        log("Live bot oprit manual.")
        send_telegram("🔴 Trading AI Bot oprit manual.")
