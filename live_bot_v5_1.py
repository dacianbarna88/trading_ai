import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd


from config.settings import (
    STARTING_CAPITAL,
    INTERVAL_SECONDS,
    MIN_SCORE_TO_BUY,
    STOP_LOSS_PCT,
    MIN_CASH_RESERVE,
    MAX_POSITIONS_BULL,
    MAX_POSITIONS_NEUTRAL,
    MAX_POSITIONS_BEAR,
    TEST_SELL_MODE,
    ALLOW_BUY_WHEN_MARKET_CLOSED,
    WATCHLIST_FILE,
    LIVE_SIGNALS_FILE,
    PORTFOLIO_FILE,
    ALERTS_FILE,
    STATUS_FILE,
)
from utils.logger import log
from core.market_regime import get_market_regime, get_max_positions
from core.status import set_status
from utils.telegram import send_telegram
from core.market_hours import is_market_open
from markets.market_hours import is_market_open as is_named_market_open
from data.storage import load_watchlist, load_csv_safe, load_portfolio, save_portfolio
from core.portfolio import get_open_positions, get_cash_available
from core.indicators import calculate_rsi, get_latest_price
from data.alerts import save_alert
from core.risk import get_dynamic_trade_size, get_score_adjusted_trade_size
from core.historical_risk import get_risk_multiplier, get_historical_risk_mode
from core.forecast_risk import get_forecast_multiplier
from core.trades import buy_position, sell_position
from core.trailing import update_trailing_state
from core.portfolio_prices import update_portfolio_prices
from research.signals import generate_signals
from research.market_scanner import run_market_scanner
from research.multi_market_scanner import main as run_multi_market_scanner
from research.global_candidates import main as run_global_candidates
from research.auto_rebalance_engine import get_auto_rebalance_plan

def get_ticker_market(ticker):
    ticker = str(ticker).upper()

    if ticker.endswith(".PA") or ticker.endswith(".DE"):
        return "EU"

    if ticker.endswith(".L"):
        return "UK"

    return "US"


def is_ticker_market_open(ticker):
    return is_named_market_open(get_ticker_market(ticker))

def log_allocation_signals():
    path = Path("allocation_signals.csv")

    if not path.exists():
        return

    try:
        df = pd.read_csv(path)

        buys = df[df["Signal"].astype(str) == "ALLOCATOR_BUY"]
        sells = df[df["Signal"].astype(str) == "ALLOCATOR_SELL"]

        log(
            f"Allocator Signals PAPER_ONLY: "
            f"BUY {len(buys)} | SELL {len(sells)}"
        )

        for _, row in df.head(10).iterrows():
            log(
                f"Allocator Signal: {row['Signal']} "
                f"{row['Ticker']} ${row['Amount_$']} "
                f"Status={row['Status']}"
            )

    except Exception as e:
        log(f"Allocator Signals error: {e}")

def manage_portfolio(signals_df):
    portfolio = load_portfolio()
    positions = get_open_positions(portfolio)

    from research_core.governance.live_advisory_runtime import (
        advisory_runtime_summary,
        get_advisory_action,
        load_live_advisory,
        should_block_new_buy,
    )
    from research_core.governance.shadow_validation_ledger import (
        log_buy_allowed,
        log_buy_blocked_by_tae,
        log_buy_skipped_other_reason,
    )

    advisory_state = load_live_advisory()
    live_bot_cycle_id = datetime.now().strftime("%Y%m%d%H%M%S")

    tae_action = get_advisory_action(advisory_state)
    block_new_buy, tae_block_reason = should_block_new_buy(advisory_state)
    log(f"TAE Live Advisory: {advisory_runtime_summary(advisory_state)}")
    if advisory_state.warning:
        log(f"TAE Live Advisory warning: {advisory_state.warning}")

    market_open = is_market_open()
    market_regime = get_market_regime()
    trade_size = get_dynamic_trade_size(signals_df, portfolio, market_regime)

    log(f"Market Regime activ: {market_regime}")
    log(
        f"Cash disponibil: ${get_cash_available(portfolio):.2f} | "
        f"Cash reserve: ${MIN_CASH_RESERVE:.2f} | "
        f"Trade size: ${trade_size:.2f}"
    )
    log(
        f"Strategic Risk: Historical {get_historical_risk_mode()} "
        f"x{get_risk_multiplier():.2f} | "
        f"Forecast x{get_forecast_multiplier():.2f}"
    )

    if not ALLOW_BUY_WHEN_MARKET_CLOSED:
        any_open_candidate = False

        if not signals_df.empty:
            strong_candidates = signals_df[signals_df["Signal"].astype(str) == "STRONG BUY"]
            any_open_candidate = any(
                is_ticker_market_open(ticker)
                for ticker in strong_candidates["Ticker"].astype(str).tolist()
            )

        if not any_open_candidate:
            log("Nicio piață relevantă deschisă pentru candidații STRONG BUY. Nu execut BUY.")

    exit_checked_tickers = set()

    for _, row in signals_df.iterrows():
        ticker = row["Ticker"]
        signal = row["Signal"]
        score = pd.to_numeric(row["Score"], errors="coerce")
        price = pd.to_numeric(row["Price"], errors="coerce")

        if pd.isna(price) or price <= 0:
            continue

        if ticker not in positions:
            if is_ticker_market_open(ticker) or ALLOW_BUY_WHEN_MARKET_CLOSED:
                if (
                    signal == "STRONG BUY"
                    and score >= MIN_SCORE_TO_BUY
                    and market_regime != "BEAR"
                ):
                    if block_new_buy:
                        log(f"BUY blocat pentru {ticker}: {tae_block_reason}")
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
                    elif len(positions) < get_max_positions(market_regime):
                        if tae_action == "BUY_ADVISORY":
                            log(f"TAE advisory supportive pentru {ticker}")
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

                elif signal == "STRONG BUY":
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

        else:
            exit_checked_tickers.add(ticker)
            avg_price = positions[ticker]["avg_price"]
            pnl_pct = ((price - avg_price) / avg_price) * 100
            portfolio, trailing_sell, trailing_stop = update_trailing_state(
                portfolio, ticker, price, avg_price
            )

            if TEST_SELL_MODE:
                portfolio = sell_position(row, portfolio, "TEST SELL MODE")
                positions = get_open_positions(portfolio)

            elif trailing_sell:
                portfolio = sell_position(
                    row,
                    portfolio,
                    f"TRAILING STOP | price {price:.2f} <= stop {trailing_stop:.2f}",
                )
                positions = get_open_positions(portfolio)

            elif pnl_pct <= STOP_LOSS_PCT:
                portfolio = sell_position(row, portfolio, f"STOP LOSS {pnl_pct:.2f}%")
                positions = get_open_positions(portfolio)

    # Safety net: a held position whose ticker failed to produce a row this
    # cycle (a transient yfinance download error, or every download failing
    # so signals_df came back empty) would otherwise silently skip its
    # STOP_LOSS/trailing-stop check for the whole cycle. Fetch a fresh price
    # directly for any such ticker so the exit check still runs.
    for ticker in list(positions.keys()):
        if ticker in exit_checked_tickers:
            continue

        fallback_price = get_latest_price(ticker)
        if fallback_price is None or fallback_price <= 0:
            log(f"Exit check sărit pentru {ticker}: preț indisponibil în acest ciclu.")
            continue

        avg_price = positions[ticker]["avg_price"]
        pnl_pct = ((fallback_price - avg_price) / avg_price) * 100
        portfolio, trailing_sell, trailing_stop = update_trailing_state(
            portfolio, ticker, fallback_price, avg_price
        )
        fallback_row = {"Ticker": ticker, "Price": fallback_price, "Score": 0, "Signal": "WAIT"}

        log(
            f"Exit check fallback pentru {ticker} (lipsă din signals_df): "
            f"preț {fallback_price:.2f} | PnL {pnl_pct:.2f}%"
        )

        if TEST_SELL_MODE:
            portfolio = sell_position(fallback_row, portfolio, "TEST SELL MODE")
            positions = get_open_positions(portfolio)

        elif trailing_sell:
            portfolio = sell_position(
                fallback_row,
                portfolio,
                f"TRAILING STOP | price {fallback_price:.2f} <= stop {trailing_stop:.2f} (fallback)",
            )
            positions = get_open_positions(portfolio)

        elif pnl_pct <= STOP_LOSS_PCT:
            portfolio = sell_position(fallback_row, portfolio, f"STOP LOSS {pnl_pct:.2f}% (fallback)")
            positions = get_open_positions(portfolio)

    save_portfolio(portfolio)



if __name__ == "__main__":
    set_status("RUNNING")
    log("Live bot pornit.")

    send_telegram(
        "🟢 Trading AI Bot pornit.\n"
        "Status: RUNNING\n"
        "Telegram: ACTIV\n"
        "Market Regime Filter: ACTIV\n"
        "Scoring V4 Step5: SMA20 + SMA50 + RSI + Volum + Breakout\n"
        f"Cash reserve: ${MIN_CASH_RESERVE:.2f}\n"
        f"Max poziții BULL/NEUTRAL/BEAR: {MAX_POSITIONS_BULL}/{MAX_POSITIONS_NEUTRAL}/{MAX_POSITIONS_BEAR}"
    )

    try:
        log("Market Scanner: rulare inițială la pornire.")
        run_market_scanner()

        log("Multi-Market Scanner: rulare inițială.")
        run_multi_market_scanner()
        run_global_candidates()

        if Path("watchlist_global.txt").exists():
            Path("watchlist.txt").write_text(Path("watchlist_global.txt").read_text())
            log("Global Execution Bridge: watchlist.txt actualizat din watchlist_global.txt.")

        plan = get_auto_rebalance_plan()
        log(f"Auto Rebalance Plan: REDUCE {plan['reduce']} | BUY {plan['buy']}")

        log_allocation_signals()

        last_scanner_run = time.time()

        while True:
            # An unhandled exception anywhere inside a cycle (network
            # error, unexpected data, a bug) must not silently kill the
            # whole process: that would permanently stop STOP_LOSS/
            # TAKE_PROFIT/trailing checks on live positions until a human
            # notices and restarts the bot. Log it, alert, and keep looping.
            try:
                if time.time() - last_scanner_run >= 1800:
                    log("Market Scanner: rulare periodică.")
                    run_market_scanner()
                    last_scanner_run = time.time()

                generate_signals(manage_portfolio, update_portfolio_prices)
            except Exception as e:
                log(f"CICLU EROARE NEAȘTEPTATĂ: {e}\n{traceback.format_exc()}")
                send_telegram(f"⚠️ Bot cycle error (continuing): {e}")

            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        set_status("STOPPED")
        log("Live bot oprit manual.")
        send_telegram("🔴 Trading AI Bot oprit manual.")