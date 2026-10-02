"""10-year historical projection of the EXACT strategies deployed live today
(tae2's core_gtaa_50, stocks/MoVo10's momentum_vt10) -- "what if these
monthly-rebalance rules had been running for the last 10 years" instead of
the ~1 week of real paper history so far. 120 monthly decisions per system
instead of waiting 10 years in real time for the same sample size.

This is a backtest, not a new idea: it calls the exact same deployable
strategy functions (tae2.engine.DEPLOYABLE / stocks.engine.DEPLOYABLE) the
live engines use, through the exact same backtest.run() both research.py
modules already use for gating. Nothing here is a new code path for the
strategies themselves -- only the "slice to 10 years, show every month"
reporting is new.

CAVEATS, read before drawing conclusions:
- stocks/MoVo10 (momentum_vt10): still carries the open survivorship-bias
  issue (today's S&P 500 membership applied to the whole 10-year window,
  not point-in-time) -- see stocks/universe.py. This projection shows how
  the MECHANICAL RULE would have behaved monthly, not a bias-free verdict.
- tae2 (core_gtaa_50): ETF universe is fixed/stable over this window, so it
  doesn't have that specific issue.
- Both numbers are still a backtest: no slippage beyond the assumed cost_bps,
  no real fills, no real data gaps the live engines would fail closed on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from stocks import config as stocks_config
from stocks import data as stocks_data
from stocks import engine as stocks_engine
from tae2 import backtest, config as tae2_config, data as tae2_data, engine as tae2_engine

STARTING_CAPITAL = 100_000.0  # matches both live paper accounts' actual Alpaca balance
YEARS_BACK = 10
OUT_DIR = Path("output")


@dataclass
class MonthlyRow:
    date: pd.Timestamp
    value: float
    monthly_return: float
    drawdown: float  # from this system's own peak-to-date, within the 10y window


def _monthly_series(res: backtest.Result, start: pd.Timestamp) -> list[MonthlyRow]:
    equity = res.equity  # daily, normalized to 1.0 at the strategy's own inception
    month_ends = backtest.month_ends(equity.index)
    monthly_equity = equity.loc[equity.index.intersection(month_ends)]
    monthly_equity = monthly_equity.loc[monthly_equity.index >= start]
    if monthly_equity.empty:
        return []
    # Rebase to STARTING_CAPITAL at the first month-end *inside the window*
    # (not at the strategy's full-history inception) so this reads like "if
    # you'd put $100k in at this point 10 years ago."
    rebased = monthly_equity / monthly_equity.iloc[0] * STARTING_CAPITAL
    rows: list[MonthlyRow] = []
    peak = rebased.iloc[0]
    prev = rebased.iloc[0]
    for d, v in rebased.items():
        peak = max(peak, v)
        monthly_return = v / prev - 1 if prev else 0.0
        drawdown = v / peak - 1
        rows.append(MonthlyRow(d, v, monthly_return, drawdown))
        prev = v
    return rows


def _summary(rows: list[MonthlyRow]) -> dict:
    if not rows:
        return {}
    values = [r.value for r in rows]
    rets = [r.monthly_return for r in rows[1:]]
    years = len(rows) / 12
    cagr = (values[-1] / values[0]) ** (1 / years) - 1 if years > 0 else 0.0
    wins = sum(1 for r in rets if r > 0)
    vol_m = pd.Series(rets).std() if len(rets) > 1 else 0.0
    sharpe = (pd.Series(rets).mean() / vol_m * (12**0.5)) if vol_m else 0.0
    return {
        "months": len(rows),
        "start_value": values[0],
        "end_value": values[-1],
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": min(r.drawdown for r in rows),
        "win_months": wins,
        "loss_months": len(rets) - wins,
        "best_month": max(rets) if rets else 0.0,
        "worst_month": min(rets) if rets else 0.0,
    }


def run() -> tuple[list[MonthlyRow], list[MonthlyRow], dict, dict]:
    now = pd.Timestamp.now(tz="UTC")
    start = (now - pd.DateOffset(years=YEARS_BACK)).tz_localize(None)

    tae2_prices, _ = tae2_data.load(refresh=False)
    tae2_weights = tae2_engine.DEPLOYABLE[tae2_engine.DEFAULT_STRATEGY](tae2_prices)
    tae2_res = backtest.run(tae2_engine.DEFAULT_STRATEGY, tae2_prices, tae2_weights, cost_bps=tae2_config.COST_BPS)
    tae2_rows = _monthly_series(tae2_res, start)

    stocks_prices, _ = stocks_data.load(refresh=False)
    stocks_weights = stocks_engine.DEPLOYABLE[stocks_engine.DEFAULT_STRATEGY](stocks_prices)
    stocks_res = backtest.run(
        stocks_engine.DEFAULT_STRATEGY, stocks_prices, stocks_weights, cost_bps=stocks_config.COST_BPS
    )
    stocks_rows = _monthly_series(stocks_res, start)

    return tae2_rows, stocks_rows, _summary(tae2_rows), _summary(stocks_rows)


def to_markdown(tae2_rows, stocks_rows, tae2_sum, stocks_sum) -> str:
    lines = [
        f"# Proiecție istorică 10 ani — {date.today().isoformat()}",
        "",
        "Simulare pe strategiile EXACTE care rulează azi (core_gtaa_50 / momentum_vt10), "
        "pe ultimii 10 ani de date reale, pornind cu $100,000 fiecare (ca la conturile reale paper).",
        "",
        "**Atenție:** MoVo10 (momentum_vt10) folosește universul de acțiuni de AZI aplicat retroactiv "
        "(survivorship bias, nerezolvat încă) — arată cum s-ar fi comportat REGULA mecanică, nu un verdict curat. "
        "tae2 nu are această problemă (universul de ETF-uri e stabil).",
        "",
        "## Rezumat",
        "",
        "| | tae2 (core_gtaa_50) | MoVo10 (momentum_vt10) |",
        "|---|---:|---:|",
        f"| Luni simulate | {tae2_sum.get('months', 0)} | {stocks_sum.get('months', 0)} |",
        f"| Valoare finală | ${tae2_sum.get('end_value', 0):,.0f} | ${stocks_sum.get('end_value', 0):,.0f} |",
        f"| CAGR | {tae2_sum.get('cagr', 0):.1%} | {stocks_sum.get('cagr', 0):.1%} |",
        f"| Sharpe (lunar, anualizat) | {tae2_sum.get('sharpe', 0):.2f} | {stocks_sum.get('sharpe', 0):.2f} |",
        f"| Cădere maximă | {tae2_sum.get('max_drawdown', 0):.1%} | {stocks_sum.get('max_drawdown', 0):.1%} |",
        f"| Luni câștigătoare / pierzătoare | {tae2_sum.get('win_months', 0)} / {tae2_sum.get('loss_months', 0)} | {stocks_sum.get('win_months', 0)} / {stocks_sum.get('loss_months', 0)} |",
        f"| Cea mai bună / proastă lună | {tae2_sum.get('best_month', 0):+.1%} / {tae2_sum.get('worst_month', 0):+.1%} | {stocks_sum.get('best_month', 0):+.1%} / {stocks_sum.get('worst_month', 0):+.1%} |",
        "",
        "## Traseu lunar complet",
        "",
        "| Data | tae2 valoare | tae2 lunar | tae2 cădere | MoVo10 valoare | MoVo10 lunar | MoVo10 cădere |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    by_date = {}
    for r in tae2_rows:
        by_date.setdefault(r.date, {})["tae2"] = r
    for r in stocks_rows:
        by_date.setdefault(r.date, {})["stocks"] = r
    for d in sorted(by_date):
        t = by_date[d].get("tae2")
        s = by_date[d].get("stocks")
        t_cells = f"${t.value:,.0f} | {t.monthly_return:+.1%} | {t.drawdown:.1%}" if t else "— | — | —"
        s_cells = f"${s.value:,.0f} | {s.monthly_return:+.1%} | {s.drawdown:.1%}" if s else "— | — | —"
        lines.append(f"| {d.date().isoformat()} | {t_cells} | {s_cells} |")
    return "\n".join(lines) + "\n"


def write_report(text: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"historical_projection_{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return path


if __name__ == "__main__":
    tae2_rows, stocks_rows, tae2_sum, stocks_sum = run()
    text = to_markdown(tae2_rows, stocks_rows, tae2_sum, stocks_sum)
    path = write_report(text)
    print(text)
    print(f"Report written to {path}")
