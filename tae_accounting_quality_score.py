"""Accounting-quality score — an adaptation of the Piotroski F-Score
(Piotroski, 2000) — Sprint 3 Phase 5.

Rather than another ad hoc ratio blend (Phase 4's tae_fundamental_quality_
score.py, tested and rejected for lack of signal), this reuses a real,
established accounting-analysis checklist built for exactly this purpose:
telling fundamentally strengthening companies from weakening ones using
only financial-statement data. 9 binary criteria across profitability,
leverage/liquidity, and operating efficiency — each compares the latest
quarter to the same quarter a year ago (LOOKBACK_QUARTERS), the way an
analyst actually reads consecutive filings, not a single snapshot.

Each criterion is 1 (pass) / 0 (fail) / None (not scoreable — a required
field is missing for this ticker, e.g. banks have no Gross Profit/COGS
concept and HSBA.L has no cash-flow statement at all via this data
source, verified 2026-09-13). compute_f_score() reports
points-earned / points-SCOREABLE, not / 9, so a company missing a field
is never penalized for data availability rather than actual weakness.

Pure functions, no network access — takes the plain nested dicts
tae_financial_statements_snapshot.py already fetched and cached.
"""

from __future__ import annotations

from typing import Any

LOOKBACK_QUARTERS = 4

NET_INCOME = "Net Income"
OPERATING_CASH_FLOW = "Operating Cash Flow"
TOTAL_ASSETS = "Total Assets"
TOTAL_DEBT = "Total Debt"
CURRENT_ASSETS = "Current Assets"
CURRENT_LIABILITIES = "Current Liabilities"
ORDINARY_SHARES_NUMBER = "Ordinary Shares Number"
GROSS_PROFIT = "Gross Profit"
TOTAL_REVENUE = "Total Revenue"

Row = dict[str, float | None]


def _periods_desc(row: Row) -> list[str]:
    return sorted(row.keys(), reverse=True)


def _latest(row: Row | None) -> float | None:
    if not row:
        return None
    periods = _periods_desc(row)
    if not periods:
        return None
    return row.get(periods[0])


def _year_ago(row: Row | None, lookback: int = LOOKBACK_QUARTERS) -> float | None:
    if not row:
        return None
    periods = _periods_desc(row)
    if len(periods) <= lookback:
        return None
    return row.get(periods[lookback])


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


# --- Profitability -----------------------------------------------------


def positive_net_income(net_income: Row) -> int | None:
    v = _latest(net_income)
    return None if v is None else int(v > 0)


def positive_operating_cash_flow(ocf: Row) -> int | None:
    v = _latest(ocf)
    return None if v is None else int(v > 0)


def roa_improving(net_income: Row, total_assets: Row) -> int | None:
    roa_now = _safe_div(_latest(net_income), _latest(total_assets))
    roa_then = _safe_div(_year_ago(net_income), _year_ago(total_assets))
    if roa_now is None or roa_then is None:
        return None
    return int(roa_now > roa_then)


def cash_flow_exceeds_net_income(ocf: Row, net_income: Row) -> int | None:
    ocf_now, ni_now = _latest(ocf), _latest(net_income)
    if ocf_now is None or ni_now is None:
        return None
    return int(ocf_now > ni_now)


# --- Leverage / liquidity ------------------------------------------------


def leverage_decreasing(total_debt: Row, total_assets: Row) -> int | None:
    lev_now = _safe_div(_latest(total_debt), _latest(total_assets))
    lev_then = _safe_div(_year_ago(total_debt), _year_ago(total_assets))
    if lev_now is None or lev_then is None:
        return None
    return int(lev_now < lev_then)


def current_ratio_improving(current_assets: Row, current_liabilities: Row) -> int | None:
    cr_now = _safe_div(_latest(current_assets), _latest(current_liabilities))
    cr_then = _safe_div(_year_ago(current_assets), _year_ago(current_liabilities))
    if cr_now is None or cr_then is None:
        return None
    return int(cr_now > cr_then)


def no_new_shares_issued(shares: Row) -> int | None:
    now, then = _latest(shares), _year_ago(shares)
    if now is None or then is None:
        return None
    return int(now <= then)


# --- Operating efficiency ------------------------------------------------


def gross_margin_improving(gross_profit: Row, revenue: Row) -> int | None:
    gm_now = _safe_div(_latest(gross_profit), _latest(revenue))
    gm_then = _safe_div(_year_ago(gross_profit), _year_ago(revenue))
    if gm_now is None or gm_then is None:
        return None
    return int(gm_now > gm_then)


def asset_turnover_improving(revenue: Row, total_assets: Row) -> int | None:
    at_now = _safe_div(_latest(revenue), _latest(total_assets))
    at_then = _safe_div(_year_ago(revenue), _year_ago(total_assets))
    if at_now is None or at_then is None:
        return None
    return int(at_now > at_then)


def compute_f_score(statements: dict[str, Any]) -> dict[str, Any]:
    """`statements` = {"income": {row_name: {period: value}}, "balance_
    sheet": {...}, "cashflow": {...}} (tae_financial_statements_snapshot's
    per-ticker output). Returns {"score": points/scoreable or None,
    "points": int, "scoreable": int, "criteria": {name: 1|0|None}}."""
    income = statements.get("income") or {}
    balance_sheet = statements.get("balance_sheet") or {}
    cashflow = statements.get("cashflow") or {}

    net_income = income.get(NET_INCOME) or {}
    revenue = income.get(TOTAL_REVENUE) or {}
    gross_profit = income.get(GROSS_PROFIT) or {}
    ocf = cashflow.get(OPERATING_CASH_FLOW) or {}
    total_assets = balance_sheet.get(TOTAL_ASSETS) or {}
    total_debt = balance_sheet.get(TOTAL_DEBT) or {}
    current_assets = balance_sheet.get(CURRENT_ASSETS) or {}
    current_liabilities = balance_sheet.get(CURRENT_LIABILITIES) or {}
    shares = balance_sheet.get(ORDINARY_SHARES_NUMBER) or {}

    criteria = {
        "positive_net_income": positive_net_income(net_income),
        "positive_operating_cash_flow": positive_operating_cash_flow(ocf),
        "roa_improving": roa_improving(net_income, total_assets),
        "cash_flow_exceeds_net_income": cash_flow_exceeds_net_income(ocf, net_income),
        "leverage_decreasing": leverage_decreasing(total_debt, total_assets),
        "current_ratio_improving": current_ratio_improving(current_assets, current_liabilities),
        "no_new_shares_issued": no_new_shares_issued(shares),
        "gross_margin_improving": gross_margin_improving(gross_profit, revenue),
        "asset_turnover_improving": asset_turnover_improving(revenue, total_assets),
    }
    scoreable = [v for v in criteria.values() if v is not None]
    points = sum(scoreable)
    score = (points / len(scoreable)) if scoreable else None
    return {"score": score, "points": points, "scoreable": len(scoreable), "criteria": criteria}
