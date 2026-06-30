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
FALLBACK_STARTING_CAPITAL = 30000.0
ACCOUNT_VALUE_FORMULA = (
    "Account Value = Starting Capital + Deposits + Realized PnL + Open Unrealized PnL"
)

st.title("🚀 Trading AI Dashboard")
st.caption(
    "TAE Command Center + Live Bot + Portfolio + Performance + Bot Health + Daily Report · "
    "UI/OBSERVABILITY ONLY"
)

from dashboard_tae_command_center import render_tae_command_center

from research_core.accounting.accounting_snapshot import (
    build_accounting_snapshot,
    load_accounting_snapshot,
)



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


TAE_REPORT_METADATA_ONLY_BYTES = 500_000
TAE_TIMESTAMP_KEYS = (
    "generated_at",
    "created_at",
    "report_date",
    "updated_at",
    "last_checkpoint_saved_at",
)
TAE_VERDICT_KEYS = ("verdict", "status", "overall_status", "health_status")


def discover_tae_report_files():
    return sorted(Path(".").glob("tae_*.json"))


def load_tae_report_file(path: Path):
    if not path.is_file():
        return None, "missing", "File not found"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, "invalid", f"Invalid JSON: {exc}"
    except OSError as exc:
        return None, "invalid", f"Read error: {exc}"
    if not isinstance(payload, dict):
        return None, "invalid", "Root element must be a JSON object"
    return payload, "ok", None


def build_tae_report_summary(payload: dict) -> str:
    parts: list[str] = []

    if payload.get("recommended_next_action"):
        parts.append(str(payload["recommended_next_action"]))

    summary = payload.get("summary")
    if isinstance(summary, str) and summary.strip():
        parts.append(summary.strip())
    elif isinstance(summary, dict) and summary:
        parts.append(json.dumps(summary, ensure_ascii=False)[:300])

    conclusions = payload.get("research_conclusions")
    if isinstance(conclusions, list):
        parts.extend(str(item) for item in conclusions[:2] if item)

    observations = payload.get("strategic_observations")
    if isinstance(observations, dict):
        confidence = observations.get("overall_ecosystem_confidence") or {}
        if isinstance(confidence, dict) and confidence.get("confidence_label"):
            parts.append(
                "Ecosystem confidence: {label} ({score})".format(
                    label=confidence.get("confidence_label"),
                    score=confidence.get("composite_score"),
                )
            )
        top = observations.get("highest_quality_strategy") or {}
        if isinstance(top, dict) and top.get("candidate_id"):
            parts.append(
                "Top strategy: {cid} ({decision})".format(
                    cid=top.get("candidate_id"),
                    decision=top.get("decision"),
                )
            )

    if "jobs_total" in payload:
        parts.append(
            "Jobs {completed}/{total} completed; blocked={blocked}; failed={failed}".format(
                completed=payload.get("jobs_completed", "?"),
                total=payload.get("jobs_total", "?"),
                blocked=payload.get("jobs_blocked", 0),
                failed=payload.get("jobs_failed", 0),
            )
        )

    if payload.get("event_count") is not None:
        parts.append(f"Events stored: {payload.get('event_count')}")

    recommendation_summary = payload.get("recommendation_summary")
    if isinstance(recommendation_summary, dict) and recommendation_summary:
        items = ", ".join(
            f"{key}={value}"
            for key, value in list(recommendation_summary.items())[:4]
        )
        parts.append(f"Recommendations: {items}")

    checks = payload.get("checks")
    if isinstance(checks, list) and checks:
        failed = [
            str(item.get("check_id"))
            for item in checks
            if isinstance(item, dict) and str(item.get("status", "")).upper() not in {"OK", "HEALTHY"}
        ]
        if failed:
            parts.append(f"Non-OK checks: {', '.join(failed[:5])}")

    return " | ".join(parts[:4]) if parts else "—"


def extract_tae_report_view(path: Path) -> dict:
    payload, state, error = load_tae_report_file(path)
    if state != "ok" or payload is None:
        return {
            "report": path.name,
            "state": state,
            "timestamp": None,
            "timestamp_key": None,
            "verdict": None,
            "summary": None,
            "warning": error,
            "file_size_kb": round(path.stat().st_size / 1024, 1) if path.is_file() else None,
        }

    timestamp = None
    timestamp_key = None
    for key in TAE_TIMESTAMP_KEYS:
        value = payload.get(key)
        if value:
            timestamp_key = key
            timestamp = value
            break

    verdict = None
    for key in TAE_VERDICT_KEYS:
        value = payload.get(key)
        if value:
            verdict = value
            break
    if verdict is None and isinstance(payload.get("ecosystem_health"), dict):
        verdict = payload["ecosystem_health"].get("overall_status")

    report_warnings = payload.get("warnings")
    warning = None
    if isinstance(report_warnings, list) and report_warnings:
        warning = "; ".join(str(item) for item in report_warnings[:3])

    return {
        "report": path.name,
        "state": "ok",
        "timestamp": timestamp,
        "timestamp_key": timestamp_key,
        "verdict": verdict,
        "summary": build_tae_report_summary(payload),
        "warning": warning,
        "file_size_kb": round(path.stat().st_size / 1024, 1),
        "schema": payload.get("schema"),
        "payload": payload,
    }


def load_tae_advisory_index():
    path = Path("tae_advisory_index.json")
    if not path.is_file():
        return None, "Advisory index not found — run tae_advisory_index_demo.py"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"Invalid advisory index: {exc}"
    if not isinstance(payload, dict):
        return None, "Advisory index root must be a JSON object"
    return payload, None


def render_tae_advisory_index_summary():
    index, error = load_tae_advisory_index()
    if error:
        st.info(error)
        return

    st.markdown("#### TAE Advisory Index")
    st.caption(
        f"{index.get('mode', 'READ_ONLY_REPORT')} | "
        f"Live trading impact: {index.get('live_trading_impact', 'NONE')}"
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total indexed", index.get("total_reports", 0))
    c2.metric("Valid", index.get("valid_reports", 0))
    c3.metric("Invalid", index.get("invalid_reports", 0))
    c4.metric(
        "Generated",
        (index.get("generated_at") or "—")[:19],
    )

    by_category = index.get("reports_by_category") or {}
    latest = index.get("latest_timestamp_by_category") or {}
    category_rows = []
    for category, files in by_category.items():
        if not files:
            continue
        category_rows.append(
            {
                "Category": category,
                "Reports": len(files),
                "Latest timestamp": latest.get(category) or "—",
            }
        )
    if category_rows:
        st.dataframe(pd.DataFrame(category_rows), width="stretch")

    notes = index.get("advisory_notes") or []
    if notes:
        with st.expander("Advisory notes", expanded=False):
            for note in notes:
                st.write(f"• {note}")

    verdict_dist = index.get("verdict_status_distribution") or {}
    if verdict_dist:
        with st.expander("Verdict / status distribution", expanded=False):
            st.json(verdict_dist)

    warnings_dist = index.get("warnings_distribution") or {}
    if warnings_dist:
        with st.expander("Warnings distribution", expanded=False):
            st.json(warnings_dist)


def render_tae_intelligence_reports():
    st.subheader("TAE Intelligence Reports")
    st.caption(
        "READ-ONLY | UI ONLY | NO_AUTO_EXECUTION | Canonical tae_*.json visibility bridge"
    )

    render_tae_advisory_index_summary()
    st.divider()

    report_paths = discover_tae_report_files()
    if not report_paths:
        st.warning("No tae_*.json reports found in project root.")
        return

    views = [extract_tae_report_view(path) for path in report_paths]
    ok_count = sum(1 for item in views if item["state"] == "ok")
    invalid_count = sum(1 for item in views if item["state"] == "invalid")

    c1, c2, c3 = st.columns(3)
    c1.metric("Reports found", len(views))
    c2.metric("Loaded OK", ok_count)
    c3.metric("Invalid JSON", invalid_count)

    overview_rows = []
    for item in views:
        overview_rows.append(
            {
                "Report": item["report"],
                "State": item["state"].upper(),
                "Timestamp": item["timestamp"] or "—",
                "Verdict / Status": item["verdict"] or "—",
                "Size (KB)": item.get("file_size_kb"),
            }
        )
    st.dataframe(pd.DataFrame(overview_rows), width="stretch")

    for item in views:
        title = item["report"]
        if item["state"] != "ok":
            with st.expander(f"⚠️ {title} — {item['state'].upper()}", expanded=False):
                st.warning(item.get("warning") or "Report unavailable")
            continue

        with st.expander(f"✅ {title}", expanded=False):
            col_a, col_b = st.columns(2)
            col_a.write(f"**Timestamp ({item['timestamp_key'] or 'n/a'}):** {item['timestamp'] or '—'}")
            col_b.write(f"**Verdict / Status:** {item['verdict'] or '—'}")
            if item.get("schema"):
                st.write(f"**Schema:** `{item['schema']}`")
            st.write(f"**Summary:** {item['summary']}")
            if item.get("warning"):
                st.warning(item["warning"])

            payload = item.get("payload") or {}
            size_kb = item.get("file_size_kb") or 0
            if size_kb * 1024 > TAE_REPORT_METADATA_ONLY_BYTES:
                st.info("Large report — metadata view only (full JSON not rendered).")
            else:
                with st.expander("Raw JSON (read-only)", expanded=False):
                    st.json(payload)


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
    # Account value = cash (starting + deposits − buys + sell proceeds) + open mark-to-market value.
    # Closed BUY rows are not included — only net-open positions contribute to open_value.
    account_value = cash + open_value
    return open_positions, cash, open_value, open_pnl, account_value


def _resolve_starting_capital() -> float:
    try:
        from config.settings import STARTING_CAPITAL as cfg_start

        return float(cfg_start)
    except (ImportError, AttributeError, TypeError, ValueError):
        return FALLBACK_STARTING_CAPITAL


def _portfolio_df_to_rows(portfolio_df: pd.DataFrame) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, series in portfolio_df.iterrows():
        row: dict[str, str] = {}
        for col in portfolio_df.columns:
            val = series[col]
            row[col] = "" if pd.isna(val) else str(val)
        rows.append(row)
    return rows


def _sum_deposits(portfolio_df: pd.DataFrame) -> float:
    if portfolio_df.empty or "Action" not in portfolio_df.columns:
        return 0.0
    df = portfolio_df.copy()
    df["Action"] = df["Action"].astype(str).str.upper()
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
    df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0)
    deposits = df[df["Action"] == "DEPOSIT"]
    if deposits.empty:
        return 0.0
    return float((deposits["Price"] * deposits["Shares"]).sum())


def _open_pnl_from_portfolio_marks(portfolio_df: pd.DataFrame) -> float:
    """Mark-to-market open PnL from latest open BUY row per ticker in portfolio.csv."""
    if portfolio_df.empty:
        return 0.0
    rows = _portfolio_df_to_rows(portfolio_df)
    net: dict[str, float] = {}
    for row in rows:
        ticker = row.get("Ticker", "").strip()
        action = row.get("Action", "").upper()
        shares = float(row.get("Shares") or 0)
        if not ticker or ticker == "CASH":
            continue
        if action == "BUY":
            net[ticker] = net.get(ticker, 0.0) + shares
        elif action == "SELL":
            net[ticker] = net.get(ticker, 0.0) - shares

    open_pnl = 0.0
    for ticker, shares in net.items():
        if shares <= 0.0001:
            continue
        ticker_rows = [r for r in rows if r.get("Ticker") == ticker]
        if not ticker_rows:
            continue
        last = ticker_rows[-1]
        if last.get("Action", "").upper() == "BUY":
            open_pnl += float(last.get("PnL") or 0)
    return round(open_pnl, 2)


def compute_dashboard_performance_metrics(
    portfolio_df: pd.DataFrame,
    open_pnl: float | None = None,
) -> dict:
    """
    Canonical dashboard performance metrics (read-only).

    account_value = starting_capital + deposits + realized_pnl + open_pnl
    """
    from tools.recompute_realized_pnl import _is_repairable_sell, recompute_portfolio

    starting_capital = _resolve_starting_capital()
    deposits = round(_sum_deposits(portfolio_df), 2)

    empty = {
        "starting_capital": starting_capital,
        "deposits": deposits,
        "realized_pnl": 0.0,
        "open_pnl": 0.0,
        "total_pnl": 0.0,
        "account_value": round(starting_capital + deposits, 2),
        "win_rate": 0.0,
        "buy_count": 0,
        "sell_count": 0,
        "repairable_sell_count": 0,
        "account_value_formula": ACCOUNT_VALUE_FORMULA,
        "legacy_account_value": round(starting_capital + deposits, 2),
        "closed_trades": [],
        "portfolio_sell_sum_all": 0.0,
        "portfolio_sell_sum_repairable": 0.0,
    }
    if portfolio_df.empty:
        return empty

    df = portfolio_df.copy()
    df["Action"] = df["Action"].astype(str).str.upper()
    buy_count = int((df["Action"] == "BUY").sum())
    sell_count = int((df["Action"] == "SELL").sum())

    rows = _portfolio_df_to_rows(portfolio_df)
    updated_rows, _changes = recompute_portfolio(rows)

    realized_pnl = 0.0
    wins = 0
    closed_trades: list[dict] = []
    portfolio_sell_sum_all = 0.0
    portfolio_sell_sum_repairable = 0.0

    for orig, corrected in zip(rows, updated_rows):
        if orig.get("Action", "").upper() != "SELL":
            continue
        stale_pnl = float(orig.get("PnL") or 0)
        portfolio_sell_sum_all += stale_pnl
        if not _is_repairable_sell(orig):
            continue
        exec_pnl = float(corrected.get("PnL") or 0)
        portfolio_sell_sum_repairable += stale_pnl
        realized_pnl += exec_pnl
        if exec_pnl > 0:
            wins += 1
        closed_trades.append(
            {
                "Date": corrected.get("Date", orig.get("Date", "")),
                "Ticker": corrected.get("Ticker", orig.get("Ticker", "")),
                "Recorded_PnL": stale_pnl,
                "Execution_PnL": exec_pnl,
                "PnL": exec_pnl,
            }
        )

    repairable_count = len(closed_trades)
    win_rate = round((wins / repairable_count * 100.0) if repairable_count else 0.0, 2)
    realized_pnl = round(realized_pnl, 2)

    if open_pnl is None:
        open_pnl = _open_pnl_from_portfolio_marks(portfolio_df)
    else:
        open_pnl = round(float(open_pnl), 2)

    total_pnl = round(realized_pnl + open_pnl, 2)
    account_value = round(starting_capital + deposits + total_pnl, 2)

    return {
        "starting_capital": starting_capital,
        "deposits": deposits,
        "realized_pnl": realized_pnl,
        "open_pnl": open_pnl,
        "total_pnl": total_pnl,
        "account_value": account_value,
        "win_rate": win_rate,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "repairable_sell_count": repairable_count,
        "account_value_formula": ACCOUNT_VALUE_FORMULA,
        "legacy_account_value": empty["legacy_account_value"],
        "closed_trades": closed_trades,
        "portfolio_sell_sum_all": round(portfolio_sell_sum_all, 2),
        "portfolio_sell_sum_repairable": round(portfolio_sell_sum_repairable, 2),
    }


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
open_positions, cash, open_value, open_pnl_live, account_value_legacy = compute_open_positions(portfolio)
dash_perf = compute_dashboard_performance_metrics(portfolio, open_pnl=open_pnl_live)
starting_capital_display = dash_perf["starting_capital"]
deposits_display = dash_perf["deposits"]
realized_pnl = dash_perf["realized_pnl"]
open_pnl_display = dash_perf["open_pnl"]
total_pnl = dash_perf["total_pnl"]
account_value_display = dash_perf["account_value"]
execution_win_rate = dash_perf["win_rate"]
stale_recorded_realized = dash_perf["portfolio_sell_sum_repairable"]
legacy_realized_pnl = dash_perf["portfolio_sell_sum_all"]
legacy_account_value = account_value_legacy
closed_trades_exec = pd.DataFrame(dash_perf["closed_trades"])
if not closed_trades_exec.empty:
    closed_trades_exec["Date"] = pd.to_datetime(closed_trades_exec["Date"], errors="coerce")

total_capital_base = starting_capital_display + deposits_display
account_return_display = (
    (total_pnl / total_capital_base) * 100 if total_capital_base else 0
)
account_pnl = account_value_legacy - total_capital_base
account_return_pct = (account_pnl / total_capital_base) * 100 if total_capital_base else 0

_accounting_snapshot, _acct_status = load_accounting_snapshot()
if _accounting_snapshot is None:
    try:
        _accounting_snapshot = build_accounting_snapshot(".")
        _acct_status = "LIVE_BUILD"
    except Exception:
        _accounting_snapshot = {}
        _acct_status = "ERROR"

tabs = st.tabs([
    "🏠 TAE Command Center",
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
    "📡 TAE Intelligence Reports",
])

with tabs[0]:
    render_tae_command_center()

with tabs[1]:
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

with tabs[2]:
    st.subheader("📜 Alerts History")
    if not alerts.empty:
        st.success(f"Am găsit {len(alerts)} alerte.")
        st.dataframe(alerts, width="stretch")
        st.download_button("⬇️ Export Alerts CSV", alerts.to_csv(index=False).encode("utf-8"), "alerts_history.csv", "text/csv")
    else:
        st.warning("Nu există alerts_log.csv")

with tabs[3]:
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

with tabs[4]:
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

with tabs[5]:
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

with tabs[6]:
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
        c4.metric("Valoare cont (legacy cash+open)", f"${account_value_legacy:,.2f}")
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

with tabs[7]:
    st.subheader("📈 Performance")
    st.caption(
        "Canonical metrics from tae_accounting_snapshot.json — corrected SELL reconciliation + capital base audit"
    )
    acct = _accounting_snapshot or {}
    if acct.get("capital_base_status") in {"NEEDS_OPERATOR_CONFIRMATION", "DOUBLE_COUNT_RISK"}:
        st.error("**CAPITAL BASE NEEDS CONFIRMATION** — virtual/test DEPOSIT excluded from contributed capital")
        for line in (acct.get("capital_base_explanation") or [])[:4]:
            st.caption(line)
    if not acct.get("portfolio_readable"):
        st.warning("portfolio.csv missing or accounting snapshot unavailable")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Effective Contributed Capital", f"${acct.get('effective_contributed_capital', 0):,.2f}")
        c2.metric("Account Value", f"${acct.get('account_value_corrected', 0):,.2f}")
        c3.metric("Trading PnL", f"${acct.get('corrected_total_trading_pnl', 0):,.2f}")
        c4.metric("Cash", f"${acct.get('cash_available', 0):,.2f}")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Realized PnL", f"${acct.get('corrected_realized_pnl', 0):,.2f}")
        c6.metric("Unrealized PnL", f"${acct.get('corrected_unrealized_pnl', 0):,.2f}")
        c7.metric("Open Positions Value", f"${acct.get('open_positions_value', 0):,.2f}")
        c8.metric("Capital Base Status", acct.get("capital_base_status", "NO_DATA"))
        st.caption(acct.get("account_value_formula", ACCOUNT_VALUE_FORMULA))
        if acct.get("capital_deposits_excluded_as_duplicate"):
            st.warning(
                f"Detected ${acct.get('capital_deposits_detected', 0):,.2f} DEPOSIT; "
                f"excluded ${acct.get('capital_deposits_excluded_as_duplicate', 0):,.2f} virtual/test — "
                f"counted toward capital: ${acct.get('capital_deposits_counted', 0):,.2f}"
            )

        winners = acct.get("top_winners_corrected") or []
        losers = acct.get("top_losers_corrected") or []
        drag = acct.get("top_drag_corrected")
        if drag:
            st.info(
                f"Top drag (corrected): {drag.get('ticker')} PnL ${drag.get('pnl'):,.2f} — "
                f"{drag.get('reason', '')}"
            )
        wcol, lcol = st.columns(2)
        with wcol:
            if winners:
                st.markdown("**Top winners (corrected realized)**")
                st.dataframe(pd.DataFrame(winners[:5]), width="stretch", hide_index=True)
        with lcol:
            if losers:
                st.markdown("**Top losers (corrected realized)**")
                st.dataframe(pd.DataFrame(losers[:5]), width="stretch", hide_index=True)

        with st.expander("LEGACY / DEPRECATED metrics (do not use for decisions)", expanded=False):
            st.warning(
                "These values use stale portfolio PnL columns or config STARTING_CAPITAL mismatch. "
                "Use corrected metrics above."
            )
            l1, l2, l3, l4 = st.columns(4)
            l1.metric("Legacy Total PnL (recompute tool)", f"${total_pnl:,.2f}")
            l2.metric("Legacy Account Value", f"${account_value_display:,.2f}")
            l3.metric("Legacy Realized (stale column)", f"${dash_perf.get('portfolio_sell_sum_repairable', 0):,.2f}")
            l4.metric("Legacy config starting capital", f"${starting_capital_display:,.2f}")
            l5, l6, l7, l8 = st.columns(4)
            l5.metric("Win Rate (legacy recompute)", f"{execution_win_rate:.2f}%")
            l6.metric("BUY / SELL count", f"{dash_perf['buy_count']} / {dash_perf['sell_count']}")
            l7.metric("Raw PnL incl. CASH rows", f"${acct.get('raw_pnl_including_cash_rows', 0):,.2f}")
            l8.metric("Prior inflated AV (+virtual dep)", f"$40,395.46")

        st.subheader("📋 Trade History")
        perf = portfolio.copy()
        perf["Date"] = pd.to_datetime(perf["Date"], errors="coerce")
        st.dataframe(perf.sort_values("Date"), width="stretch")
        st.subheader("✅ Closed Trades (legacy recompute — see snapshot for corrected)")
        closed = closed_trades_exec.copy()
        if not closed.empty:
            st.dataframe(closed, width="stretch")
        else:
            st.info("Nu există încă tranzacții închise.")

with tabs[8]:
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

with tabs[9]:
    st.subheader("📋 Daily Report")
    st.caption("PnL: realized SELL execution PnL + open mark-to-market PnL")
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
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Starting Capital", f"${starting_capital_display:,.2f}")
        c2.metric("Deposits", f"${deposits_display:,.2f}")
        c3.metric("Realized PnL", f"${realized_pnl:,.2f}")
        c4.metric("Open PnL", f"${open_pnl_display:,.2f}")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Total PnL", f"${total_pnl:,.2f}")
        c6.metric("Account Value", f"${account_value_display:,.2f}")
        c7.metric("Win Rate", f"{execution_win_rate:.2f}%")
        c8.metric("Randament cont", f"{account_return_display:.2f}%")
        c9, c10, c11, c12 = st.columns(4)
        c9.metric("BUY", dash_perf["buy_count"])
        c10.metric("SELL", dash_perf["sell_count"])
        c11.metric("Cash (legacy view)", f"${cash:,.2f}")
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

Starting Capital: ${starting_capital_display:,.2f}
Deposits: ${deposits_display:,.2f}
Realized PnL: ${realized_pnl:,.2f}
Open PnL: ${open_pnl_display:,.2f}
Total PnL: ${total_pnl:,.2f}
Account Value: ${account_value_display:,.2f}
{ACCOUNT_VALUE_FORMULA}
Randament cont: {account_return_display:.2f}%

BUY: {dash_perf['buy_count']}
SELL: {dash_perf['sell_count']}
Win Rate: {execution_win_rate:.2f}%
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


with tabs[11]:
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


with tabs[10]:
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

        hist_cols = [
            "Ticker", "Score", "Signal",
            "Historical_Edge", "Historical_Win_Rate", "Historical_Avg_Return",
            "Historical_Sharpe", "Strategy_Rank", "Committee_Score", "Historical_Confidence",
        ]
        strong_hist_cols = [c for c in hist_cols if c in pro.columns]
        if len(strong) > 0 and len(strong_hist_cols) >= 4:
            st.subheader("📜 STRONG BUY — Historical Intelligence")
            st.dataframe(strong[strong_hist_cols], width="stretch")
        elif len(strong) > 0:
            st.caption("Historical enrichment columns not yet present — run scanner refresh enrich step.")

        research_cols = [
            "Ticker", "Score", "Signal",
            "Research_Momentum", "Research_Sector", "Research_Regional", "Research_Macro",
            "Research_ETF", "Research_Threshold", "Research_Counterfactual", "Research_Confidence",
        ]
        strong_research_cols = [c for c in research_cols if c in pro.columns]
        if len(strong) > 0 and len(strong_research_cols) >= 4:
            st.subheader("🔬 STRONG BUY — Research Runtime")
            st.dataframe(strong[strong_research_cols], width="stretch")
        elif len(strong) > 0:
            st.caption("Research enrichment columns not yet present — run scanner refresh research step.")

        committee_cols = [
            "Ticker", "Score", "Signal",
            "Committee_Decision", "Committee_Confidence", "Committee_Weighted_Score",
            "Committee_Adaptive_Weight", "Committee_Votes", "Committee_Accuracy",
        ]
        strong_committee_cols = [c for c in committee_cols if c in pro.columns]
        if len(strong) > 0 and len(strong_committee_cols) >= 4:
            st.subheader("🏛 STRONG BUY — Committee Runtime")
            st.dataframe(strong[strong_committee_cols], width="stretch")
        elif len(strong) > 0:
            st.caption("Committee enrichment columns not yet present — run scanner refresh committee step.")

        allocation_cols = [
            "Ticker", "Score", "Signal",
            "Allocation_Score", "Allocation_Confidence", "Regional_Strength",
            "Allocation_Sector", "Allocation_Macro", "Allocation_Bias",
            "Capital_Flow", "Strategic_Portfolio_Score",
        ]
        strong_alloc_cols = [c for c in allocation_cols if c in pro.columns]
        if len(strong) > 0 and len(strong_alloc_cols) >= 4:
            st.subheader("📊 STRONG BUY — Strategic Allocation")
            st.dataframe(strong[strong_alloc_cols], width="stretch")
        elif len(strong) > 0:
            st.caption("Allocation enrichment columns not yet present — run scanner refresh allocation step.")

        meta_cols = [
            "Ticker", "Score", "Signal",
            "Meta_Score", "Meta_Confidence", "Meta_Health", "Meta_Strategy_Rank",
            "Meta_Ecosystem_Status", "Unified_Runtime_Score",
        ]
        strong_meta_cols = [c for c in meta_cols if c in pro.columns]
        if len(strong) > 0 and len(strong_meta_cols) >= 4:
            st.subheader("🧠 STRONG BUY — Meta Intelligence")
            st.dataframe(strong[strong_meta_cols], width="stretch")
        elif len(strong) > 0:
            st.caption("Meta enrichment columns not yet present — run scanner refresh meta step.")

        if "Unified_Runtime_Score" in pro.columns and len(strong) > 0:
            st.subheader("🏆 Top Unified Runtime Candidates")
            unified = strong.sort_values("Unified_Runtime_Score", ascending=False)
            ucols = [c for c in ["Ticker", "Score", "Unified_Runtime_Score", "Meta_Score", "Signal"] if c in unified.columns]
            st.dataframe(unified[ucols].head(10), width="stretch")

        unified_ssot_path = Path("tae_unified_runtime.json")
        if unified_ssot_path.is_file():
            try:
                with unified_ssot_path.open(encoding="utf-8") as handle:
                    unified_ssot = json.load(handle)
                strategy_global = unified_ssot.get("strategy_global") or {}
                strategy_summary = (unified_ssot.get("advisory_summary") or {}).get("strategy_summary") or strategy_global
                if strategy_summary:
                    st.subheader("🧬 STRATEGY DISCOVERY & SIMULATION")
                    st.caption(
                        f"Discovery avg confidence: {strategy_summary.get('discovery_avg_confidence')} · "
                        f"Simulation confidence: {strategy_summary.get('simulation_confidence')}"
                    )
                    top_sim = strategy_summary.get("top_simulated_strategies") or []
                    top_disc = strategy_summary.get("top_discovered_strategies") or []
                    if top_disc:
                        st.markdown("**Top Discovered Strategies**")
                        st.dataframe(pd.DataFrame(top_disc[:10]), width="stretch")
                    if top_sim:
                        st.markdown("**Top Simulated Strategies**")
                        st.dataframe(pd.DataFrame(top_sim[:10]), width="stretch")
                cf_global = unified_ssot.get("counterfactual_global") or {}
                if cf_global:
                    st.subheader("🧠 EVENT MEMORY & COUNTERFACTUAL")
                    st.caption(
                        f"Entry: {cf_global.get('entry_verdict')} · Exit: {cf_global.get('exit_verdict')} · "
                        f"Shadow events: {cf_global.get('shadow_total_events')} · "
                        f"Alt return: {cf_global.get('expected_alternative_return')}"
                    )
                eco_global = unified_ssot.get("ecosystem_global") or {}
                if eco_global:
                    st.subheader("🌐 ECOSYSTEM / EVIDENCE / DAILY INTELLIGENCE")
                    st.caption(
                        f"Run: {eco_global.get('ecosystem_run_status')} · "
                        f"Evidence: {eco_global.get('evidence_verdict')} · "
                        f"Gate: {eco_global.get('evidence_gate')} · "
                        f"Daily score: {eco_global.get('daily_intelligence_score')}"
                    )
                summary = unified_ssot.get("advisory_summary") or {}
                top_unified = summary.get("top_unified_candidates") or []
                if top_unified:
                    st.subheader("🔗 UNIFIED RUNTIME SSOT")
                    st.caption(
                        f"Records: {summary.get('record_count')} · "
                        f"Avg score: {(summary.get('unified_runtime_score_summary') or {}).get('avg')} · "
                        f"Avg confidence: {(summary.get('confidence_summary') or {}).get('avg')}"
                    )
                    st.dataframe(pd.DataFrame(top_unified[:10]), width="stretch")
                    with st.expander("Expand Unified Runtime Records", expanded=False):
                        for rec in (unified_ssot.get("records_list") or [])[:10]:
                            ticker = rec.get("Ticker")
                            st.markdown(
                                f"**{ticker}** — score={rec.get('Unified_Runtime_Score')} "
                                f"confidence={rec.get('Unified_Runtime_Confidence')} "
                                f"recommendation={rec.get('Unified_Runtime_Recommendation')}"
                            )
                            st.json(rec)
            except (OSError, json.JSONDecodeError, ValueError):
                st.caption("Unified runtime SSOT present but could not be parsed.")

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


with tabs[12]:
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


with tabs[13]:
    render_tae_intelligence_reports()


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
