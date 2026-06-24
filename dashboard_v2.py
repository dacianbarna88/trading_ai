import os
from pathlib import Path

import pandas as pd
import json
from pathlib import Path
from data.storage import load_portfolio
from core.portfolio import get_cash_available, get_open_positions
from core.market_regime import get_max_positions
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="Trading AI Dashboard", page_icon="🚀", layout="wide")

from config.settings import STARTING_CAPITAL
MARKET_REGIME_TICKER = "SPY"
MARKET_REGIME_SMA = 200
TRAILING_STOP_PCT = 5

st.title("🚀 Trading AI Dashboard")
st.caption("Dashboard complet: Live Bot + Portfolio + Performance + Bot Health + Daily Report")



def load_json(filename):
    try:
        path = Path(filename)
        if not path.exists():
            return {}
        return json.loads(path.read_text())
    except Exception:
        return {}

def load_csv(name):
    path = Path(name)
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception as e:
            st.error(f"Eroare la citire {name}: {e}")
    return pd.DataFrame()


def read_text(name):
    path = Path(name)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""


def get_live_price(ticker):
    try:
        data = yf.download(ticker, period="5d", auto_adjust=False, progress=False)

        if data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            close = data[("Close", ticker)].dropna()
        else:
            close = data["Close"].dropna()

        if close.empty:
            return None

        return float(close.iloc[-1])

    except Exception:
        return None


def get_market_regime():
    try:
        data = yf.download(MARKET_REGIME_TICKER, period="2y", auto_adjust=False, progress=False)

        if data.empty:
            return "UNKNOWN", None, None

        if isinstance(data.columns, pd.MultiIndex):
            close = data[("Close", MARKET_REGIME_TICKER)].dropna()
        else:
            close = data["Close"].dropna()

        if close.empty:
            return "UNKNOWN", None, None

        sma = close.rolling(MARKET_REGIME_SMA).mean().dropna()

        if sma.empty:
            return "UNKNOWN", float(close.iloc[-1]), None

        last_close = float(close.iloc[-1])
        last_sma = float(sma.iloc[-1])

        return ("BULL" if last_close > last_sma else "BEAR"), last_close, last_sma

    except Exception:
        return "UNKNOWN", None, None


def last_log_contains(pattern):
    lines = read_text("bot_output.log").splitlines()
    for line in reversed(lines):
        if pattern in line:
            return line
    return "N/A"


def compute_open_positions(portfolio_df):
    if portfolio_df.empty:
        return pd.DataFrame(), STARTING_CAPITAL, 0, 0, STARTING_CAPITAL

    df = portfolio_df.copy()

    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce")

    df["Action"] = df["Action"].astype(str).str.upper()

    buys = df[df["Action"] == "BUY"]
    sells = df[df["Action"] == "SELL"]
    deposits = df[df["Action"] == "DEPOSIT"]

    spent = (buys["Price"] * buys["Shares"]).sum()
    received = (sells["Price"] * sells["Shares"]).sum()
    deposited = (deposits["Price"] * deposits["Shares"]).sum() if not deposits.empty else 0

    cash = STARTING_CAPITAL + deposited - spent + received

    open_rows = []
    for ticker in df["Ticker"].dropna().unique():
        rows = df[df["Ticker"] == ticker]
        buy_rows = rows[rows["Action"].astype(str).str.upper() == "BUY"]
        sell_rows = rows[rows["Action"].astype(str).str.upper() == "SELL"]
        buy_shares = buy_rows["Shares"].sum()
        sell_shares = sell_rows["Shares"].sum()
        open_shares = buy_shares - sell_shares

        if open_shares > 0:
            avg_price = (buy_rows["Price"] * buy_rows["Shares"]).sum() / buy_shares
            current_price = get_live_price(ticker) or avg_price
            invested = open_shares * avg_price
            current_value = open_shares * current_price
            pnl = current_value - invested
            pnl_pct = (pnl / invested) * 100 if invested else 0
            row = {
                "Ticker": ticker,
                "Shares": open_shares,
                "Avg_Price": avg_price,
                "Current_Price": current_price,
                "Invested": invested,
                "Current_Value": current_value,
                "PnL": pnl,
                "PnL_%": pnl_pct,
            }
            if "Highest_Price" in rows.columns:
                highest_price = pd.to_numeric(rows["Highest_Price"], errors="coerce").max()
                if not pd.isna(highest_price):
                    row["Highest_Price"] = highest_price
                    row["Drop_From_High_%"] = ((current_price - highest_price) / highest_price) * 100
            if "Highest_PnL_%" in rows.columns:
                highest_pnl = pd.to_numeric(rows["Highest_PnL_%"], errors="coerce").max()
                if not pd.isna(highest_pnl):
                    row["Highest_PnL_%"] = highest_pnl
            open_rows.append(row)

    open_positions = pd.DataFrame(open_rows)
    open_value = open_positions["Current_Value"].sum() if not open_positions.empty else 0
    open_pnl = open_positions["PnL"].sum() if not open_positions.empty else 0
    account_value = cash + open_value
    return open_positions, cash, open_value, open_pnl, account_value


def prepare_live_signals(df):
    if df.empty:
        return df
    out = df.copy()
    if "Score" in out.columns:
        out["Score"] = pd.to_numeric(out["Score"], errors="coerce")
        out = out.sort_values("Score", ascending=False)
    if "RSI" in out.columns:
        out["RSI"] = pd.to_numeric(out["RSI"], errors="coerce").round(2)
    if "Price" in out.columns:
        out["Price"] = pd.to_numeric(out["Price"], errors="coerce").round(2)
    return out


def get_trailing_active_positions(open_positions_df):
    if open_positions_df.empty or "Drop_From_High_%" not in open_positions_df.columns:
        return pd.DataFrame()
    df = open_positions_df.copy()
    if "Highest_Price" not in df.columns:
        return pd.DataFrame()
    df["Trailing_Stop_Est"] = df["Highest_Price"] * (1 - TRAILING_STOP_PCT / 100)
    return df[df["Current_Price"] >= df["Trailing_Stop_Est"]].copy()


signals = load_csv("signals.csv")
alerts = load_csv("alerts_log.csv")
optimization = load_csv("optimization_results.csv")
live_signals = load_csv("live_signals.csv")
portfolio = load_csv("portfolio.csv")

bot_status = read_text("bot_status.txt").strip() or "UNKNOWN"
market_regime, market_price, market_sma = get_market_regime()
open_positions, cash, open_value, open_pnl, account_value = compute_open_positions(portfolio)

deposited_capital = 0
if not portfolio.empty and "Action" in portfolio.columns:
    tmp_capital_df = portfolio.copy()
    tmp_capital_df["Action"] = tmp_capital_df["Action"].astype(str).str.upper()
    tmp_capital_df["Price"] = pd.to_numeric(tmp_capital_df["Price"], errors="coerce")
    tmp_capital_df["Shares"] = pd.to_numeric(tmp_capital_df["Shares"], errors="coerce")
    dep_rows = tmp_capital_df[tmp_capital_df["Action"] == "DEPOSIT"]
    deposited_capital = (dep_rows["Price"] * dep_rows["Shares"]).sum() if not dep_rows.empty else 0

total_capital_base = STARTING_CAPITAL + deposited_capital
account_pnl = account_value - total_capital_base
account_return_pct = (account_pnl / total_capital_base) * 100 if total_capital_base else 0

tabs = st.tabs([
    "📊 Dashboard",
    "📜 Alerts",
    "⚙️ Optimization",
    "🛡 Risk Manager",
    "🤖 Live Bot",
    "💰 Portfolio",
    "📈 Performance",
    "🩺 Bot Health",
    "📋 Daily Report",
    "📡 Live Signals Pro",
    "🧠 Investment Committee",
    "🧪 Strategic Validation",
])

with tabs[0]:
    st.subheader("📊 Control Center")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bot Status", bot_status)
    if market_price is not None and market_sma is not None:
        c2.metric("Market Regime", market_regime, f"{MARKET_REGIME_TICKER} {market_price:.2f} / SMA{MARKET_REGIME_SMA} {market_sma:.2f}")
    else:
        c2.metric("Market Regime", market_regime)
    c3.metric("Trailing Stop", "ACTIV", f"{TRAILING_STOP_PCT}%")
    c4.metric("Daily Report Telegram", "ACTIV", "23:05")

    if market_regime == "BULL":
        st.success("🟢 Market Regime: BULL — BUY permis când piața este deschisă.")
    elif market_regime == "BEAR":
        st.error("🔴 Market Regime: BEAR — BUY blocat de filtru.")
    else:
        st.warning("⚠️ Market Regime necunoscut.")

    st.divider()
    st.subheader("🌍 Global Candidates")

    global_df = load_csv("global_candidates.csv")
    if not global_df.empty:
        g1, g2, g3 = st.columns(3)
        g1.metric("Candidați globali", len(global_df))
        g2.metric("Global STRONG BUY", int((global_df["Signal"].astype(str) == "STRONG BUY").sum()))
        g3.metric("Piețe", int(global_df["Market"].nunique()) if "Market" in global_df.columns else 0)

        cols = [c for c in [
            "Market", "Ticker", "Score", "Signal", "News_Bias",
            "Allocation_Weight", "Exit_Score", "Exit_Warning", "Market_Open", "Price"
        ] if c in global_df.columns]

        st.dataframe(global_df[cols].head(30), width="stretch")
    else:
        st.warning("Nu găsesc global_candidates.csv")

    st.divider()
    st.subheader("🔁 Global Rebalance")

    rebalance_df = load_csv("global_rebalance_recommendations.csv")
    if not rebalance_df.empty:
        r1, r2, r3 = st.columns(3)
        r1.metric("REDUCE", int((rebalance_df["Action"].astype(str) == "REDUCE").sum()))
        r2.metric("REVIEW", int((rebalance_df["Action"].astype(str) == "REVIEW").sum()))
        r3.metric("HOLD", int((rebalance_df["Action"].astype(str) == "HOLD").sum()))

        cols = [c for c in ["Ticker", "Action", "Reason", "Score", "Exit_Warning", "Market"] if c in rebalance_df.columns]
        st.dataframe(rebalance_df[cols], width="stretch")
    else:
        st.warning("Nu găsesc global_rebalance_recommendations.csv")

    st.divider()
    st.subheader("🧠 Strategic Command Center")

    c1, c2, c3, c4 = st.columns(4)

    try:
        portfolio_live = load_portfolio()
        open_pos = get_open_positions(portfolio_live)
        cash_now = get_cash_available(portfolio_live)
        max_pos = get_max_positions("BULL")

        c1.metric("Cash", f"${cash_now:,.2f}")
        c2.metric("Open Positions", len(open_pos))
        c3.metric("Max Positions", max_pos)
        c4.metric("Free Slots", max_pos - len(open_pos))
    except Exception as e:
        st.warning(f"Nu pot calcula portfolio metrics: {e}")

    strategic_txt = Path("strategic_decision_summary.txt").read_text() if Path("strategic_decision_summary.txt").exists() else "Nu găsesc strategic_decision_summary.txt"
    st.text(strategic_txt)

    st.divider()
    st.subheader("🧬 Adaptive Allocation Engine — PAPER ONLY")

    adaptive_txt = read_text("adaptive_allocation_summary.txt").strip()
    if adaptive_txt:
        st.text(adaptive_txt)
    else:
        st.warning("Nu găsesc adaptive_allocation_summary.txt")

    adaptive_json = load_json("adaptive_allocation.json")
    if adaptive_json:
        recommended = adaptive_json.get("recommended_allocation", {})
        strength = adaptive_json.get("strength", {})

        a1, a2, a3 = st.columns(3)
        a1.metric("US Recommended", f"{recommended.get('US', 0)}%")
        a2.metric("EU Recommended", f"{recommended.get('EU', 0)}%")
        a3.metric("UK Recommended", f"{recommended.get('UK', 0)}%")

        s1, s2, s3 = st.columns(3)
        s1.metric("US Strength", strength.get("US", 0))
        s2.metric("EU Strength", strength.get("EU", 0))
        s3.metric("UK Strength", strength.get("UK", 0))

    st.caption("Adaptive Allocation is PAPER_ONLY. No broker. No automatic execution.")

    st.divider()
    st.subheader("📊 Allocation Gap Analyzer — PAPER ONLY")

    gap_txt = read_text("allocation_gap_summary.txt").strip()
    if gap_txt:
        st.text(gap_txt)
    else:
        st.warning("Nu găsesc allocation_gap_summary.txt")

    gap_json = load_json("allocation_gap_analysis.json")
    if gap_json:
        g1, g2, g3 = st.columns(3)

        us = gap_json.get("US", {})
        eu = gap_json.get("EU", {})
        uk = gap_json.get("UK", {})

        g1.metric("US Gap", f"{us.get('gap', 0)}%", us.get("action", ""))
        g2.metric("EU Gap", f"{eu.get('gap', 0)}%", eu.get("action", ""))
        g3.metric("UK Gap", f"{uk.get('gap', 0)}%", uk.get("action", ""))

    st.caption("Gap Analyzer is PAPER_ONLY. No broker. No automatic execution.")

    st.divider()
    st.subheader("🛡️ Strategic Risk Dashboard — PAPER ONLY")

    risk_txt = read_text("strategic_risk_summary.txt").strip()

    historical_mult = 0.0
    forecast_mult = 0.0
    effective_risk = 0.0

    if risk_txt:
        risk_lines = risk_txt.splitlines()

        for i, line in enumerate(risk_lines):
            if line.strip() == "Historical Multiplier:":
                historical_mult = float(risk_lines[i + 1])

            if line.strip() == "Forecast Multiplier:":
                forecast_mult = float(risk_lines[i + 1])

            if line.strip() == "Effective Risk:":
                effective_risk = float(risk_lines[i + 1])

        m1, m2, m3 = st.columns(3)
        m1.metric("Historical Multiplier", historical_mult)
        m2.metric("Forecast Multiplier", forecast_mult)
        m3.metric("Effective Risk", effective_risk)

        st.text(risk_txt)
    else:
        st.warning("Nu găsesc strategic_risk_summary.txt")

    st.caption("Strategic Risk Dashboard is PAPER_ONLY. No broker. No automatic execution.")

    st.divider()
    st.subheader("🧠 Adaptive Strategic Risk — PAPER ONLY")

    adaptive_risk_txt = read_text("adaptive_strategic_risk_summary.txt").strip()

    if adaptive_risk_txt:
        base_risk = 0.0
        suggested_risk = 0.0
        risk_delta = 0.0
        market_regime = "UNKNOWN"
        strong_buy_count = 0

        lines = adaptive_risk_txt.splitlines()

        for line in lines:
            if line.startswith("Base Effective Risk:"):
                base_risk = float(line.split(":", 1)[1].strip())

            if line.startswith("Suggested Risk:"):
                suggested_risk = float(line.split(":", 1)[1].strip())

            if line.startswith("Risk Delta:"):
                risk_delta = float(line.split(":", 1)[1].strip())

            if line.startswith("Market Regime:"):
                market_regime = line.split(":", 1)[1].strip()

            if line.startswith("Strong Buy Count:"):
                strong_buy_count = int(float(line.split(":", 1)[1].strip()))

        ar1, ar2, ar3, ar4 = st.columns(4)

        ar1.metric("Base Risk", base_risk)
        ar2.metric("Suggested Risk", suggested_risk)
        ar3.metric("Risk Delta", risk_delta)
        ar4.metric("Market Regime", market_regime)

        ar5, ar6 = st.columns(2)
        ar5.metric("Strong Buy Count", strong_buy_count)
        ar6.metric("Status", "PAPER_ONLY")

        st.text(adaptive_risk_txt)

    else:
        st.warning("Nu găsesc adaptive_strategic_risk_summary.txt")

    st.caption("Adaptive Strategic Risk is PAPER_ONLY. No broker. No automatic execution.")

    st.divider()
    st.subheader("🧠 Strategic Conflict Detector — PAPER ONLY")

    conflict_txt = read_text("strategic_conflict_summary.txt").strip()

    if conflict_txt:
        high_count = conflict_txt.count("Conflict HIGH")
        medium_count = conflict_txt.count("Conflict MEDIUM")
        total_conflicts = high_count + medium_count

        c1, c2, c3 = st.columns(3)
        c1.metric("High Conflicts", high_count)
        c2.metric("Medium Conflicts", medium_count)
        c3.metric("Total Conflicts", total_conflicts)

        st.text(conflict_txt)
    else:
        st.warning("Nu găsesc strategic_conflict_summary.txt")

    st.caption("Strategic Conflict Detector is PAPER_ONLY. No broker. No automatic execution.")

    st.divider()
    st.subheader("🧪 Strategic Rebalance Simulator — PAPER ONLY")

    rebalance_txt = read_text("strategic_rebalance_summary.txt").strip()
    if rebalance_txt:
        st.text(rebalance_txt)
    else:
        st.warning("Nu găsesc strategic_rebalance_summary.txt")

    rebalance_json = load_json("strategic_rebalance_simulation.json")
    if rebalance_json:
        r1, r2, r3 = st.columns(3)
        r1.metric(
            "Projected Strategic Score",
            rebalance_json.get("projected_strategic_score", 0),
        )
        r2.metric(
            "Projected Allocator Health",
            rebalance_json.get("projected_allocator_health", 0),
        )
        r3.metric(
            "Alignment After",
            f"{rebalance_json.get('alignment_after', 0)}%",
        )

    st.caption("Rebalance Simulator is PAPER_ONLY. No broker. No automatic execution.")

    st.divider()
    st.subheader("🌍 Global Allocation")
    alloc_df = load_csv("global_allocations.csv")
    if not alloc_df.empty:
        st.dataframe(alloc_df, width="stretch")
    else:
        st.warning("Nu găsesc global_allocations.csv")

    st.divider()
    st.subheader("🏆 Global Top Opportunities")
    ranking_df = load_csv("global_opportunity_ranking.csv")
    if not ranking_df.empty:
        cols = [c for c in ["Market", "Ticker", "Global_Rank_Score", "Score", "Signal", "Market_Open", "Exit_Warning"] if c in ranking_df.columns]
        st.dataframe(ranking_df[cols].head(10), width="stretch")
    else:
        st.warning("Nu găsesc global_opportunity_ranking.csv")

    st.divider()
    st.subheader("⭐ Strategic Portfolio Score")

    score_df = load_csv("strategic_portfolio_score.csv")
    if not score_df.empty:
        row = score_df.iloc[0]

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Strategic Score", row["Strategic_Portfolio_Score"])
        s2.metric("Allocator Health", row["Allocator_Health"])
        s3.metric("Migration Progress", f"{row['Migration_Progress']}%")
        s4.metric("Horizon Bonus", row["Horizon_Bonus"])

        st.progress(int(row["Strategic_Portfolio_Score"]))
    else:
        st.warning("Nu găsesc strategic_portfolio_score.csv")

    st.divider()
    st.subheader("🔮 Allocation Drift Forecast")

    forecast_df = load_csv("allocation_drift_forecast.csv")
    if not forecast_df.empty:
        st.dataframe(forecast_df, width="stretch")

        try:
            st.line_chart(
                forecast_df.set_index("Cycle")["Forecast_Health"]
            )
        except Exception as e:
            st.warning(f"Nu pot afișa grafic forecast: {e}")
    else:
        st.warning("Nu găsesc allocation_drift_forecast.csv")

    st.divider()
    st.subheader("🚚 Migration Progress Tracker")

    progress_df = load_csv("migration_progress.csv")
    if not progress_df.empty:
        p1, p2, p3 = st.columns(3)

        row = progress_df.iloc[0]

        p1.metric("Migration Progress", f"{row['Progress_%']}%")
        p2.metric("Remaining Capital", f"${row['Remaining_Capital_$']:,.2f}")
        p3.metric("Cycles Remaining", row["Estimated_Cycles_Remaining"])

        st.progress(int(row["Progress_%"]))
    else:
        st.warning("Nu găsesc migration_progress.csv")

    st.divider()
    st.subheader("🩺 Allocator Health Monitor")

    health_df = load_csv("allocator_health.csv")
    if not health_df.empty:
        total_gap = health_df["Gap_%"].abs().sum()
        health_score = max(0, round(100 - total_gap / 2, 1))

        h1, h2 = st.columns(2)
        h1.metric("Allocator Health Score", health_score)
        h2.metric("Total Allocation Drift", round(total_gap, 1))

        st.dataframe(health_df, width="stretch")
    else:
        st.warning("Nu găsesc allocator_health.csv")

    st.divider()
    st.subheader("📡 Allocation Signals — PAPER ONLY")

    alloc_signals_df = load_csv("allocation_signals.csv")
    if not alloc_signals_df.empty:
        a1, a2, a3 = st.columns(3)
        a1.metric("BUY Signals", int((alloc_signals_df["Signal"].astype(str) == "ALLOCATOR_BUY").sum()))
        a2.metric("SELL Signals", int((alloc_signals_df["Signal"].astype(str) == "ALLOCATOR_SELL").sum()))
        total_amount = alloc_signals_df["Amount_$"].sum()
        a3.metric("Total Amount", "${:,.2f}".format(total_amount))

        cols = [c for c in ["Ticker", "Market", "Signal", "Amount_$", "Source", "Status"] if c in alloc_signals_df.columns]
        st.dataframe(alloc_signals_df[cols], width="stretch")
    else:
        st.warning("Nu găsesc allocation_signals.csv")

    st.divider()
    st.subheader("📊 Portfolio Construction Plan")

    construction_df = load_csv("portfolio_construction_plan.csv")
    if not construction_df.empty:
        st.dataframe(construction_df, width="stretch")
    else:
        st.warning("Nu găsesc portfolio_construction_plan.csv")

    st.divider()
    st.subheader("🔁 Rebalance Plan")
    rebalance_df = load_csv("global_rebalance_recommendations.csv")
    if not rebalance_df.empty:
        cols = [c for c in ["Ticker", "Action", "Reason", "Score", "Exit_Warning", "Market"] if c in rebalance_df.columns]
        st.dataframe(rebalance_df[cols], width="stretch")
    else:
        st.warning("Nu găsesc global_rebalance_recommendations.csv")

    st.divider()
    st.subheader("🔎 Scanner Status")

    scanner_df = load_csv("watchlist_candidates.csv")
    if not scanner_df.empty:
        total_scanned = len(scanner_df)
        strong_buy_count = int((scanner_df["Signal"].astype(str) == "STRONG BUY").sum()) if "Signal" in scanner_df.columns else 0
        eligible_new = 0

        if "Held" in scanner_df.columns and "Signal" in scanner_df.columns:
            held_bool = scanner_df["Held"].astype(str).str.upper().isin(["TRUE", "1", "YES"])
            eligible_new = int(((scanner_df["Signal"].astype(str) == "STRONG BUY") & (~held_bool)).sum())

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Tickere scanate", total_scanned)
        s2.metric("STRONG BUY", strong_buy_count)
        s3.metric("Eligibili noi", eligible_new)
        s4.metric("Watchlist curent", len(live_signals) if not live_signals.empty else 0)

        cols = [c for c in ["Ticker", "Technical_Score", "News_Bias", "News_Adjustment", "Score", "Dynamic_Min_Score", "Allocation_Weight", "Exit_Score", "Exit_Warning", "Signal", "Held", "Price", "RSI", "Breakout_20"] if c in scanner_df.columns]
        st.dataframe(scanner_df[cols].head(20), width="stretch")
    else:
        st.warning("Nu găsesc watchlist_candidates.csv sau este gol.")

    st.divider()
    st.subheader("🧠 Historical Intelligence")

    hist_summary = read_text("historical_pattern_summary.txt").strip()
    hist_df = load_csv("historical_patterns.csv")

    if hist_summary:
        st.text(hist_summary)
    else:
        st.warning("Nu găsesc historical_pattern_summary.txt")

    if not hist_df.empty:
        cols = [c for c in [
            "Date", "Similarity_%", "Forward_21d_%", "Forward_63d_%",
            "Forward_126d_%", "Forward_252d_%"
        ] if c in hist_df.columns]

        st.dataframe(hist_df[cols].head(10), width="stretch")
    else:
        st.warning("Nu găsesc historical_patterns.csv")

    st.divider()
    st.subheader("🔮 Market Forecast")

    forecast_summary = read_text("market_forecast_summary.txt").strip()
    forecast_df = load_csv("market_forecast.csv")

    if forecast_summary:
        st.text(forecast_summary)
    else:
        st.warning("Nu găsesc market_forecast_summary.txt")

    if not forecast_df.empty:
        st.dataframe(forecast_df, width="stretch")
    else:
        st.warning("Nu găsesc market_forecast.csv")

    st.divider()
    st.subheader("📰 News Intelligence")

    news_summary = load_csv("news_sentiment_summary.csv")
    if not news_summary.empty:
        n1, n2, n3 = st.columns(3)
        n1.metric("Tickere cu știri", len(news_summary))
        n2.metric("News POSITIVE", int((news_summary["News_Bias"].astype(str) == "POSITIVE").sum()))
        n3.metric("News NEGATIVE", int((news_summary["News_Bias"].astype(str) == "NEGATIVE").sum()))

        cols = [c for c in [
            "Ticker", "News_Count", "Sentiment_Total", "Sentiment_Avg",
            "Positive_Count", "Negative_Count", "Neutral_Count", "News_Bias"
        ] if c in news_summary.columns]

        st.dataframe(news_summary[cols].sort_values("Sentiment_Total", ascending=False), width="stretch")
    else:
        st.warning("Nu găsesc news_sentiment_summary.csv")

    st.divider()
    st.subheader("📊 Semnale curente")
    if not signals.empty:
        st.success(f"Am găsit {len(signals)} semnale.")
        st.dataframe(signals, width="stretch")
        if "Score" in signals.columns:
            signals["Score"] = pd.to_numeric(signals["Score"], errors="coerce")
            st.metric("Scor mediu", f"{signals['Score'].mean():.2f}")
            if "Ticker" in signals.columns:
                st.subheader("📈 Score pe ticker")
                st.bar_chart(signals.set_index("Ticker")["Score"])
    else:
        st.warning("Nu găsesc signals.csv")

with tabs[1]:
    st.subheader("📜 Alerts History")
    if not alerts.empty:
        st.success(f"Am găsit {len(alerts)} alerte.")
        st.dataframe(alerts, width="stretch")
        st.download_button("⬇️ Export Alerts CSV", alerts.to_csv(index=False).encode("utf-8"), "alerts_history.csv", "text/csv")
    else:
        st.warning("Nu există alerts_log.csv")

with tabs[2]:
    st.subheader("⚙️ Optimization")
    if not optimization.empty:
        st.success(f"Am găsit {len(optimization)} rezultate.")
        st.dataframe(optimization, width="stretch")
        if "Return" in optimization.columns:
            optimization["Return"] = pd.to_numeric(optimization["Return"], errors="coerce")
            st.subheader("🏆 Top 10 rezultate")
            st.dataframe(optimization.sort_values("Return", ascending=False).head(10), width="stretch")
    else:
        st.warning("Nu găsesc optimization_results.csv")

with tabs[3]:
    st.subheader("🛡 Risk Manager")
    capital = st.number_input("Capital cont ($)", min_value=100, value=STARTING_CAPITAL, step=100)
    risk_pct = st.slider("Risc per tranzacție (%)", 1, 10, 2)
    stop_loss_pct = st.slider("Stop Loss (%)", 1, 20, 5)
    max_loss = capital * risk_pct / 100
    position_size = max_loss / (stop_loss_pct / 100)
    c1, c2, c3 = st.columns(3)
    c1.metric("Pierdere maximă", f"${max_loss:,.2f}")
    c2.metric("Poziție recomandată", f"${position_size:,.2f}")
    c3.metric("Stop Loss", f"{stop_loss_pct}%")

with tabs[4]:
    st.subheader("🤖 Live Bot")
    try:
        from bot_controller import start_bot, stop_bot, get_status
        status = read_text("bot_status.txt").strip() or get_status()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Bot", status)
        c2.metric("Market Regime", market_regime)
        c3.metric("Trailing Stop", "ACTIV", f"{TRAILING_STOP_PCT}%")
        c4.metric("Daily Report", "ACTIV")

        b1, b2, b3 = st.columns(3)
        if status == "RUNNING":
            with b2:
                if st.button("⏹ Stop Bot"):
                    st.warning(stop_bot())
                    st.rerun()
        else:
            with b1:
                if st.button("▶️ Start Bot"):
                    st.success(start_bot())
                    st.rerun()
        with b3:
            if st.button("🔄 Refresh"):
                st.rerun()

        st.subheader("🧠 Funcții active")
        st.success("✅ Market Regime Filter: ACTIV")
        st.success("✅ Daily Report Telegram: ACTIV")
        st.success(f"✅ Trailing Stop: ACTIV ({TRAILING_STOP_PCT}%)")

        st.subheader("📄 Ultimele statusuri din log")
        st.code("\n".join([
            last_log_contains("Market Regime"),
            last_log_contains("Daily Report"),
            last_log_contains("Trailing"),
            last_log_contains("portfolio.csv actualizat"),
        ]))

        if not live_signals.empty:
            st.subheader("📡 Live Signals")
            st.dataframe(live_signals, width="stretch")
        else:
            st.info("Nu există încă live_signals.csv sau este gol.")
    except Exception as e:
        st.warning(f"Live Bot indisponibil: {e}")

with tabs[5]:
    st.subheader("💰 Portfolio")
    if portfolio.empty:
        st.warning("Nu există portfolio.csv")
    else:
        st.success(f"Am găsit {len(portfolio)} tranzacții în portofoliu.")
        st.dataframe(portfolio, width="stretch")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Capital total", f"${STARTING_CAPITAL:,.2f}")
        c2.metric("Cash disponibil", f"${cash:,.2f}")
        c3.metric("Valoare poziții", f"${open_value:,.2f}")
        c4.metric("Valoare cont", f"${account_value:,.2f}")
        c5, c6, c7 = st.columns(3)
        c5.metric("PnL cont", f"${account_pnl:,.2f}")
        c6.metric("Randament cont", f"{account_return_pct:.2f}%")
        c7.metric("Poziții deschise", len(open_positions))
        if cash < 500:
            st.warning("🟠 CASH LOW: cash sub $500. Botul are puțin spațiu pentru oportunități noi.")
        st.subheader("📌 Poziții deschise")
        if not open_positions.empty:
            st.dataframe(open_positions, width="stretch")
            st.bar_chart(open_positions.set_index("Ticker")["Current_Value"])
            st.bar_chart(open_positions.set_index("Ticker")["PnL"])
        else:
            st.info("Nu există poziții deschise.")

with tabs[6]:
    st.subheader("📈 Performance")
    if portfolio.empty:
        st.warning("Nu există portfolio.csv")
    else:
        perf = portfolio.copy()
        perf["Date"] = pd.to_datetime(perf["Date"], errors="coerce")
        perf["Price"] = pd.to_numeric(perf["Price"], errors="coerce")
        perf["Shares"] = pd.to_numeric(perf["Shares"], errors="coerce")
        perf["PnL"] = pd.to_numeric(perf.get("PnL", 0), errors="coerce").fillna(0)
        perf = perf.dropna(subset=["Date", "Ticker", "Action", "Price", "Shares"]).sort_values("Date")
        buy_count = len(perf[perf["Action"].astype(str).str.upper() == "BUY"])
        sell_count = len(perf[perf["Action"].astype(str).str.upper() == "SELL"])
        closed = perf[perf["Action"].astype(str).str.upper() == "SELL"].copy()
        realized_pnl = closed["PnL"].sum() if not closed.empty else 0
        win_rate = (len(closed[closed["PnL"] > 0]) / len(closed) * 100) if not closed.empty else 0
        total_pnl = realized_pnl + open_pnl
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("BUY", buy_count)
        c2.metric("SELL", sell_count)
        c3.metric("Win Rate", f"{win_rate:.2f}%")
        c4.metric("Realized PnL", f"${realized_pnl:,.2f}")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Open PnL", f"${open_pnl:,.2f}")
        c6.metric("Total PnL", f"${total_pnl:,.2f}")
        c7.metric("Valoare cont", f"${account_value:,.2f}")
        c8.metric("Randament cont", f"{account_return_pct:.2f}%")
        st.subheader("📋 Trade History")
        st.dataframe(perf, width="stretch")
        st.subheader("✅ Closed Trades")
        if not closed.empty:
            st.dataframe(closed, width="stretch")
        else:
            st.info("Nu există încă tranzacții închise.")

with tabs[7]:
    st.subheader("🩺 Bot Health")
    bot_log = read_text("bot_output.log")
    last_logs = bot_log.splitlines()[-20:] if bot_log else []
    last_signal_time = "N/A"
    if not live_signals.empty and "Time" in live_signals.columns:
        last_signal_time = str(live_signals["Time"].iloc[0])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bot Status", bot_status)
    c2.metric("Ultimul semnal", last_signal_time)
    c3.metric("Poziții deschise", len(open_positions))
    c4.metric("Cash disponibil", f"${cash:,.2f}")
    h1, h2, h3 = st.columns(3)
    h1.metric("Market Regime Filter", "ACTIV")
    h2.metric("Trailing Stop", "ACTIV", f"{TRAILING_STOP_PCT}%")
    h3.metric("Daily Report Telegram", "ACTIV")
    st.subheader("📄 Ultimele loguri bot")
    if last_logs:
        st.code("\n".join(last_logs))
    else:
        st.info("Nu există bot_output.log")

with tabs[8]:
    st.subheader("📋 Daily Report")
    if portfolio.empty:
        st.warning("Nu există portfolio.csv")
    else:
        report_df = portfolio.copy()
        report_df["Action"] = report_df["Action"].astype(str).str.upper()
        report_df["Price"] = pd.to_numeric(report_df["Price"], errors="coerce")
        report_df["Shares"] = pd.to_numeric(report_df["Shares"], errors="coerce")
        report_df["PnL"] = pd.to_numeric(report_df.get("PnL", 0), errors="coerce").fillna(0)
        buys = report_df[report_df["Action"] == "BUY"]
        sells = report_df[report_df["Action"] == "SELL"]
        realized_pnl = sells["PnL"].sum() if not sells.empty else 0
        total_pnl = realized_pnl + open_pnl
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Capital inițial", f"${STARTING_CAPITAL:,.2f}")
        c2.metric("Cash", f"${cash:,.2f}")
        c3.metric("Valoare poziții", f"${open_value:,.2f}")
        c4.metric("Valoare cont", f"${account_value:,.2f}")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Open PnL", f"${open_pnl:,.2f}")
        c6.metric("Realized PnL", f"${realized_pnl:,.2f}")
        c7.metric("Total PnL", f"${total_pnl:,.2f}")
        c8.metric("Randament cont", f"{account_return_pct:.2f}%")
        c9, c10, c11, c12 = st.columns(4)
        c9.metric("BUY", len(buys))
        c10.metric("SELL", len(sells))
        c11.metric("Win Rate", f"{(len(sells[sells['PnL'] > 0]) / len(sells) * 100) if not sells.empty else 0:.2f}%")
        c12.metric("Poziții deschise", len(open_positions))
        st.subheader("🏆 Top Winner / Top Loser")
        if not open_positions.empty:
            winner = open_positions.sort_values("PnL", ascending=False).iloc[0]
            loser = open_positions.sort_values("PnL", ascending=True).iloc[0]
            w1, w2 = st.columns(2)
            w1.success(f"Top Winner: {winner['Ticker']} | PnL ${winner['PnL']:.2f} | {winner['PnL_%']:.2f}%")
            w2.error(f"Top Loser: {loser['Ticker']} | PnL ${loser['PnL']:.2f} | {loser['PnL_%']:.2f}%")
        else:
            st.info("Nu există poziții deschise pentru winner/loser.")
        st.subheader("📌 Poziții deschise")
        if not open_positions.empty:
            st.dataframe(open_positions, width="stretch")
        else:
            st.info("Nu există poziții deschise.")
        report_text = f"""
Daily Trading Report

Capital initial: ${STARTING_CAPITAL:,.2f}
Cash: ${cash:,.2f}
Valoare pozitii: ${open_value:,.2f}
Valoare cont: ${account_value:,.2f}

Open PnL: ${open_pnl:,.2f}
Realized PnL: ${realized_pnl:,.2f}
Total PnL: ${total_pnl:,.2f}
Randament cont: {account_return_pct:.2f}%

BUY: {len(buys)}
SELL: {len(sells)}
Pozitii deschise: {len(open_positions)}
"""
        st.subheader("📋 Raport text")
        st.code(report_text)
        st.download_button("⬇️ Export Daily Report TXT", report_text.encode("utf-8"), "daily_report.txt", "text/plain")

        st.divider()
        st.subheader("🧠 V12.7 Position Intelligence")

        pos_intel = load_csv("position_intelligence_report.csv")
        pos_summary = read_text("position_intelligence_summary.txt").strip()

        if not pos_intel.empty:
            st.dataframe(pos_intel, width="stretch")
        else:
            st.info("Nu există încă position_intelligence_report.csv")

        if pos_summary:
            st.code(pos_summary)


with tabs[10]:
    st.subheader("🧠 Investment Committee — V9 PAPER ONLY")

    committee_txt = read_text("strategic_committee_summary.txt").strip()
    action_txt = read_text("portfolio_action_summary.txt").strip()
    decision_txt = read_text("paper_trading_decision_summary.txt").strip()
    accuracy_txt = read_text("decision_accuracy_report.txt").strip()
    history_txt = read_text("decision_history.log").strip()

    def extract_line_value(txt, label, default="N/A"):
        for line in txt.splitlines():
            if line.startswith(label):
                return line.split(":", 1)[1].strip()
        return default

    committee_vote = extract_line_value(committee_txt, "Committee Vote")
    confidence = extract_line_value(committee_txt, "Confidence")
    high_conflicts = extract_line_value(committee_txt, "High Conflicts")
    medium_conflicts = extract_line_value(committee_txt, "Medium Conflicts")

    recommended_action = extract_line_value(action_txt, "Recommended Action")
    cash_deployment = extract_line_value(action_txt, "Suggested Cash Deployment")
    risk_stance = extract_line_value(action_txt, "Risk Stance")

    approved_avg = extract_line_value(accuracy_txt, "Approved Average")
    rejected_avg = extract_line_value(accuracy_txt, "Rejected Average")
    committee_edge = extract_line_value(accuracy_txt, "Committee Edge")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Committee Vote", committee_vote)
    c2.metric("Confidence", confidence)
    c3.metric("Committee Edge", committee_edge)
    c4.metric("Cash Deployment", cash_deployment)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Recommended Action", recommended_action)
    c6.metric("Risk Stance", risk_stance)
    c7.metric("High Conflicts", high_conflicts)
    c8.metric("Medium Conflicts", medium_conflicts)

    st.divider()
    st.subheader("📊 Decision Accuracy")

    a1, a2, a3 = st.columns(3)
    a1.metric("Approved Average", approved_avg)
    a2.metric("Rejected Average", rejected_avg)
    a3.metric("Committee Edge", committee_edge)

    if accuracy_txt:
        st.text(accuracy_txt)
    else:
        st.warning("Nu găsesc decision_accuracy_report.txt")

    st.divider()
    st.subheader("✅ Paper Trading Decision")

    if decision_txt:
        st.text(decision_txt)
    else:
        st.warning("Nu găsesc paper_trading_decision_summary.txt")

    st.divider()
    st.subheader("🧠 Strategic Committee Details")

    if committee_txt:
        st.text(committee_txt)
    else:
        st.warning("Nu găsesc strategic_committee_summary.txt")

    st.divider()
    st.subheader("💼 Portfolio Action Engine")

    if action_txt:
        st.text(action_txt)
    else:
        st.warning("Nu găsesc portfolio_action_summary.txt")


    st.divider()
    st.subheader("🧠 Committee Learning Analytics — V9.5")

    learning_txt = read_text("committee_learning_summary.txt").strip()
    analytics_txt = read_text("committee_learning_analytics.txt").strip()
    learning_df = load_csv("committee_learning_history.csv")

    def extract_learning_value(txt, label, default="N/A"):
        lines = txt.splitlines()
        for i, line in enumerate(lines):
            if line.strip() == label:
                if i + 1 < len(lines):
                    return lines[i + 1].strip()
            if line.startswith(label):
                return line.split(":", 1)[1].strip()
        return default

    records = extract_learning_value(analytics_txt, "Records:")
    avg_edge = extract_learning_value(analytics_txt, "Average Edge:")
    avg_confidence = extract_learning_value(analytics_txt, "Average Confidence:")
    avg_deployment = extract_learning_value(analytics_txt, "Average Deployment:")
    best_vote = extract_learning_value(analytics_txt, "Best Vote:")
    best_vote_edge = extract_learning_value(analytics_txt, "Best Vote Edge:")

    l1, l2, l3 = st.columns(3)
    l1.metric("Learning Records", records)
    l2.metric("Average Edge", avg_edge)
    l3.metric("Average Confidence", avg_confidence)

    l4, l5, l6 = st.columns(3)
    l4.metric("Average Deployment", avg_deployment)
    l5.metric("Best Vote", best_vote)
    l6.metric("Best Vote Edge", best_vote_edge)

    if analytics_txt:
        st.text(analytics_txt)
    else:
        st.warning("Nu găsesc committee_learning_analytics.txt")

    if not learning_df.empty:
        st.subheader("📈 Committee Learning History")
        st.dataframe(learning_df, width="stretch")

        if len(learning_df) < 5:
            st.info(
                "📊 Graficele V9.7 devin relevante după minimum 5 learning records. "
                f"Momentan avem {len(learning_df)} records."
            )
        else:
            if "Committee_Edge" in learning_df.columns and "Timestamp" in learning_df.columns:
                try:
                    chart_df = learning_df.copy()
                    chart_df["Committee_Edge"] = pd.to_numeric(chart_df["Committee_Edge"], errors="coerce")
                    st.subheader("📈 Committee Edge History")
                    st.line_chart(chart_df.set_index("Timestamp")["Committee_Edge"])
                except Exception as e:
                    st.warning(f"Nu pot afișa grafic learning edge: {e}")

            if "Confidence" in learning_df.columns and "Timestamp" in learning_df.columns:
                try:
                    chart_df = learning_df.copy()
                    chart_df["Confidence"] = pd.to_numeric(chart_df["Confidence"], errors="coerce")
                    st.subheader("📊 Confidence History")
                    st.line_chart(chart_df.set_index("Timestamp")["Confidence"])
                except Exception as e:
                    st.warning(f"Nu pot afișa grafic confidence: {e}")

            if "Cash_Deployment" in learning_df.columns and "Timestamp" in learning_df.columns:
                try:
                    chart_df = learning_df.copy()
                    chart_df["Cash_Deployment"] = pd.to_numeric(chart_df["Cash_Deployment"], errors="coerce")
                    st.subheader("📉 Cash Deployment History")
                    st.line_chart(chart_df.set_index("Timestamp")["Cash_Deployment"])
                except Exception as e:
                    st.warning(f"Nu pot afișa grafic cash deployment: {e}")

            if "Committee_Vote" in learning_df.columns:
                try:
                    vote_counts = learning_df["Committee_Vote"].value_counts().reset_index()
                    vote_counts.columns = ["Vote", "Count"]
                    st.subheader("🏆 Vote Distribution")
                    st.bar_chart(vote_counts.set_index("Vote")["Count"])
                except Exception as e:
                    st.warning(f"Nu pot afișa distribuția voturilor: {e}")
    else:
        st.warning("Nu găsesc committee_learning_history.csv")



    st.divider()
    st.subheader("📜 Decision History")

    if history_txt:
        st.code(history_txt[-3000:])
    else:
        st.warning("Nu găsesc decision_history.log")

    st.caption("Investment Committee is PAPER_ONLY. No broker. No automatic execution.")


with tabs[9]:
    st.subheader("📡 Live Signals Pro")
    st.caption("Semnale sortate după Score, utile pentru monitorizarea deciziilor de BUY.")

    if live_signals.empty:
        st.info("Nu există încă live_signals.csv sau este gol.")
    else:
        pro = prepare_live_signals(live_signals)
        score_col = pd.to_numeric(pro.get("Score", pd.Series(dtype=float)), errors="coerce")
        strong = pro[(pro.get("Signal", "").astype(str) == "STRONG BUY") & (score_col >= 90)] if "Signal" in pro.columns else pro[score_col >= 90]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tickere analizate", len(pro))
        c2.metric("STRONG BUY", len(strong))
        c3.metric("Score maxim", f"{score_col.max():.0f}" if not score_col.empty else "N/A")
        c4.metric("Score mediu", f"{score_col.mean():.1f}" if not score_col.empty else "N/A")

        if len(strong) >= 10:
            st.warning("🟠 Multe semnale STRONG BUY. Filtrul poate fi permisiv pentru sesiunea curentă.")
        elif len(strong) == 0:
            st.info("Nu există STRONG BUY peste pragul curent. Botul va aștepta.")
        else:
            st.success(f"{len(strong)} oportunități peste pragul de BUY.")

        preferred_cols = [
            "Time", "Ticker", "Price", "Score", "Signal", "RSI",
            "SMA20", "SMA50", "Volume", "Avg_Volume_20", "Breakout_20"
        ]
        visible_cols = [c for c in preferred_cols if c in pro.columns]

        st.subheader("🏆 Top oportunități")
        st.dataframe(pro[visible_cols].head(15), width="stretch")

        if "Score" in pro.columns and "Ticker" in pro.columns:
            st.subheader("📊 Score pe ticker")
            st.bar_chart(pro.set_index("Ticker")["Score"])

        st.subheader("🛡 Trailing monitor")
        trailing_df = get_trailing_active_positions(open_positions)
        if trailing_df.empty:
            st.info("Nu există poziții cu trailing estimat activ în acest moment.")
        else:
            cols = [c for c in ["Ticker", "Current_Price", "Highest_Price", "Trailing_Stop_Est", "PnL_%", "Drop_From_High_%"] if c in trailing_df.columns]
            st.success(f"{len(trailing_df)} poziții monitorizate pentru trailing.")
            st.dataframe(trailing_df[cols], width="stretch")


with tabs[11]:
    st.subheader("🧪 Strategic Validation Engine — V20 to V26")
    st.caption("ANALYSIS_ONLY / NO_AUTO_CHANGE / PAPER_ONLY / NO_BROKER")

    st.divider()
    st.subheader("🧠 Vote History")
    vote_history_df = load_csv("vote_history.csv")
    if not vote_history_df.empty:
        st.dataframe(vote_history_df, width="stretch")
    else:
        st.warning("Nu găsesc vote_history.csv")

    st.divider()
    st.subheader("📊 Vote Accuracy")
    vote_accuracy_df = load_csv("vote_accuracy.csv")
    if not vote_accuracy_df.empty:
        st.dataframe(vote_accuracy_df, width="stretch")
    else:
        st.warning("Nu găsesc vote_accuracy.csv")

    st.divider()
    st.subheader("🏛 Vote Outcome Registry")
    registry_df = load_csv("vote_outcome_registry.csv")
    if not registry_df.empty:
        st.dataframe(registry_df, width="stretch")
    else:
        st.warning("Nu găsesc vote_outcome_registry.csv")

    st.divider()
    st.subheader("⚖️ Weighted Committee")
    weighted_txt = read_text("weighted_committee_summary.txt").strip()
    if weighted_txt:
        st.code(weighted_txt)
    else:
        st.warning("Nu găsesc weighted_committee_summary.txt")

    st.divider()
    st.subheader("🧬 Confidence Evolution")
    confidence_txt = read_text("confidence_evolution_summary.txt").strip()
    if confidence_txt:
        st.code(confidence_txt)
    else:
        st.warning("Nu găsesc confidence_evolution_summary.txt")

    st.divider()
    st.subheader("✅ Outcome Validation")
    outcome_txt = read_text("outcome_validation_summary.txt").strip()
    if outcome_txt:
        st.code(outcome_txt)
    else:
        st.warning("Nu găsesc outcome_validation_summary.txt")

    st.divider()
    st.subheader("🧱 Benchmark Vote Map")
    benchmark_map_df = load_csv("benchmark_vote_map.csv")
    if not benchmark_map_df.empty:
        st.dataframe(benchmark_map_df, width="stretch")
    else:
        st.warning("Nu găsesc benchmark_vote_map.csv")

    st.divider()
    st.subheader("🛡 Benchmark Execution Protection")
    benchmark_exec_txt = read_text("benchmark_execution_protected_summary.txt").strip()
    if benchmark_exec_txt:
        st.code(benchmark_exec_txt)
    else:
        st.warning("Nu găsesc benchmark_execution_protected_summary.txt")

    st.divider()
    st.subheader("📦 Benchmark Data Layer")
    benchmark_data_txt = read_text("benchmark_data_layer_summary.txt").strip()
    if benchmark_data_txt:
        st.code(benchmark_data_txt)
    else:
        st.warning("Nu găsesc benchmark_data_layer_summary.txt")

    st.divider()
    st.subheader("📈 Benchmark Price History")
    price_df = load_csv("benchmark_price_history.csv")
    if not price_df.empty:
        st.dataframe(price_df, width="stretch")
    else:
        st.warning("Nu găsesc benchmark_price_history.csv")

    st.divider()
    st.subheader("📉 Return Tracking")
    return_txt = read_text("return_tracking_summary.txt").strip()
    if return_txt:
        st.code(return_txt)
    else:
        st.warning("Nu găsesc return_tracking_summary.txt")


    st.divider()
    st.subheader("🧠 Learning Automation — V27")
    learning_txt = read_text("learning_automation_summary.txt").strip()
    if learning_txt:
        st.code(learning_txt)
    else:
        st.warning("Nu găsesc learning_automation_summary.txt")



# ===== V27.4 DASHBOARD WEIGHT HISTORY PANEL =====

st.subheader("V27.4 Learning Weight History")

if os.path.exists("learning_weight_history.csv"):
    weight_history = pd.read_csv("learning_weight_history.csv")

    st.dataframe(
        weight_history.tail(50),
        use_container_width=True
    )

    if len(weight_history) > 0:
        chart_data = weight_history.pivot_table(
            index="Timestamp",
            columns="Vote",
            values="Weight"
        )

        st.line_chart(chart_data)

else:
    st.info("learning_weight_history.csv nu există încă.")


# ===== V27.9 DASHBOARD WEIGHTED DECISION PANEL =====

st.subheader("V27.9 Weighted Committee Decision")

if os.path.exists("weighted_committee_decision_summary.txt"):
    summary_text = Path(
        "weighted_committee_decision_summary.txt"
    ).read_text()

    st.text(summary_text)

else:
    st.info("weighted_committee_decision_summary.txt nu există încă.")

# ===== V28.3 ADAPTIVE DECISION GUARD PANEL =====

st.subheader("V28.3 Adaptive Decision Guard")

if os.path.exists("adaptive_decision_guard_summary.txt"):

    guard_text = Path(
        "adaptive_decision_guard_summary.txt"
    ).read_text()

    st.text(guard_text)

else:
    st.info(
        "adaptive_decision_guard_summary.txt nu există încă."
    )

# ===== V28.9 DASHBOARD OUTCOME PANEL =====

st.subheader("V28.9 Decision Outcome Registry")

if os.path.exists("decision_registry.csv"):
    decision_registry = pd.read_csv("decision_registry.csv")

    st.dataframe(
        decision_registry.tail(50),
        use_container_width=True
    )
else:
    st.info("decision_registry.csv nu există încă.")

if os.path.exists("outcome_evaluator_summary.txt"):
    outcome_summary = Path(
        "outcome_evaluator_summary.txt"
    ).read_text()

    st.text(outcome_summary)
else:
    st.info("outcome_evaluator_summary.txt nu există încă.")

# ===== V29.2 FEEDBACK LOOP PANEL =====

st.subheader("V29.2 Feedback Learning Loop")

if os.path.exists("feedback_update_summary.txt"):

    feedback_text = Path(
        "feedback_update_summary.txt"
    ).read_text()

    st.text(feedback_text)

else:
    st.info(
        "feedback_update_summary.txt nu există încă."
    )

# ===== V29.7 SESSION INTELLIGENCE =====

st.subheader("V29.7 Session Intelligence")

if os.path.exists("market_session_snapshots.csv"):

    snapshots = pd.read_csv(
        "market_session_snapshots.csv"
    )

    st.dataframe(
        snapshots.tail(100),
        use_container_width=True
    )

else:

    st.info(
        "market_session_snapshots.csv nu există încă."
    )

if os.path.exists(
    "session_intelligence_summary.txt"
):

    session_text = Path(
        "session_intelligence_summary.txt"
    ).read_text()

    st.text(session_text)

else:

    st.info(
        "session_intelligence_summary.txt nu există încă."
    )

# ===== V29.9 MARKET READINESS SCORE =====

st.subheader("V29.9 Market Readiness")

if os.path.exists(
    "market_readiness_score_summary.txt"
):

    readiness_text = Path(
        "market_readiness_score_summary.txt"
    ).read_text()

    st.text(readiness_text)

else:

    st.info(
        "market_readiness_score_summary.txt nu există încă."
    )

# ===== V30.2 DECISION QUALITY =====

st.subheader("V30.2 Decision Quality")

if os.path.exists(
    "decision_quality_summary.txt"
):

    quality_text = Path(
        "decision_quality_summary.txt"
    ).read_text()

    st.text(quality_text)

else:

    st.info(
        "decision_quality_summary.txt nu există încă."
    )

# ===== V30.4 CONFIDENCE CALIBRATION =====

st.subheader("V30.4 Confidence Calibration")

if os.path.exists(
    "confidence_calibration_summary.txt"
):

    calibration_text = Path(
        "confidence_calibration_summary.txt"
    ).read_text()

    st.text(calibration_text)

else:

    st.info(
        "confidence_calibration_summary.txt nu există încă."
    )

# ===== V30.7 LEARNING HEALTH =====

st.subheader("V30.7 Learning Health")

if os.path.exists(
    "learning_health_summary.txt"
):

    learning_health_text = Path(
        "learning_health_summary.txt"
    ).read_text()

    st.text(
        learning_health_text
    )

else:

    st.info(
        "learning_health_summary.txt nu există încă."
    )

# ===== V30.9 MASTER INTELLIGENCE SCORE =====

st.subheader("V30.9 Master Intelligence Score")

if os.path.exists(
    "master_intelligence_score_summary.txt"
):

    master_text = Path(
        "master_intelligence_score_summary.txt"
    ).read_text()

    st.text(master_text)

else:

    st.info(
        "master_intelligence_score_summary.txt nu există încă."
    )

# ===== V31.2 DECISION REPLAY =====

st.subheader("V31.2 Decision Replay Engine")

if os.path.exists(
    "decision_replay_summary.txt"
):

    replay_text = Path(
        "decision_replay_summary.txt"
    ).read_text()

    st.text(replay_text)

else:

    st.info(
        "decision_replay_summary.txt nu există încă."
    )

# ===== V31.4 PATTERN DISCOVERY =====

st.subheader("V31.4 Pattern Discovery")

if os.path.exists(
    "pattern_discovery_summary.txt"
):

    pattern_text = Path(
        "pattern_discovery_summary.txt"
    ).read_text()

    st.text(pattern_text)

else:

    st.info(
        "pattern_discovery_summary.txt nu există încă."
    )

# ===== V31.6 LEARNING RECOMMENDATIONS =====

st.subheader("V31.6 Learning Recommendations")

if os.path.exists(
    "learning_recommendations_engine_summary.txt"
):

    recommendations_text = Path(
        "learning_recommendations_engine_summary.txt"
    ).read_text()

    st.text(recommendations_text)

else:

    st.info(
        "learning_recommendations_engine_summary.txt nu există încă."
    )

# ===== V31.8 CONFIDENCE OPTIMIZER =====

st.subheader("V31.8 Confidence Optimizer")

if os.path.exists(
    "confidence_optimizer_summary.txt"
):

    optimizer_text = Path(
        "confidence_optimizer_summary.txt"
    ).read_text()

    st.text(optimizer_text)

else:

    st.info(
        "confidence_optimizer_summary.txt nu există încă."
    )

# ===== V32.2 DAILY INTELLIGENCE RUNNER =====

st.subheader("V32.2 Daily Intelligence Runner")

if os.path.exists(
    "daily_intelligence_report.txt"
):

    daily_text = Path(
        "daily_intelligence_report.txt"
    ).read_text()

    st.text(daily_text)

else:

    st.info(
        "daily_intelligence_report.txt nu există încă."
    )
