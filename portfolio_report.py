"""Nightly portfolio report, both paper accounts (tae2 + stocks/MoVo10).

Read-only: only ever calls .account()/.positions() on each broker, never
.submit(). Meant to run once a weekday evening after the US market closes
(deploy/run_portfolio_report.sh + deploy/com.portfolio.report.plist), but
safe to run any time by hand: `python3 portfolio_report.py`.

Full names: tae2's 13-ETF universe is fixed and small, so it's a hand-
written mapping (real fund names, checked against each issuer). The stocks
universe is the ~500-name S&P 500 list, which changes over time, so names
come from stocks.universe.load_names() -- the same Wikipedia table
stocks/universe.py already caches tickers from (one fetch, both uses), not
a second network source.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from tae2.broker import AlpacaPaper as Tae2Broker
from tae2.broker import BrokerError, Position
from stocks import universe
from stocks.broker import from_env as stocks_broker_from_env

OUT_DIR = Path("output")

# tae2's fixed 13-ETF universe: real fund names, not tae2.config.UNIVERSE's
# category descriptions -- the user asked for the ETF's actual name.
ETF_NAMES: dict[str, str] = {
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust",
    "IWM": "iShares Russell 2000 ETF",
    "EFA": "iShares MSCI EAFE ETF",
    "EEM": "iShares MSCI Emerging Markets ETF",
    "VNQ": "Vanguard Real Estate ETF",
    "DBC": "Invesco DB Commodity Index Tracking Fund",
    "GLD": "SPDR Gold Shares",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "IEF": "iShares 7-10 Year Treasury Bond ETF",
    "LQD": "iShares iBoxx $ Investment Grade Corporate Bond ETF",
    "TIP": "iShares TIPS Bond ETF",
    "SHY": "iShares 1-3 Year Treasury Bond ETF",
}


def resolve_name(symbol: str, stock_names: dict[str, str]) -> str:
    """Full ETF/company name for `symbol`, or the bare symbol if unknown."""
    return ETF_NAMES.get(symbol) or stock_names.get(symbol) or symbol


@dataclass
class AccountReport:
    label: str
    equity: float
    cash: float
    positions: list[Position]
    error: str | None = None


def _fetch(label: str, make_broker) -> AccountReport:
    """Bug found 2026-10-02: a launchd catch-up run fired right after the
    Mac woke from sleep, before networking was back up -- requests raised
    ConnectionError, not BrokerError, and since that wasn't caught here it
    crashed main() before collect() returned, so the OTHER (reachable)
    account's report was lost too and no file/notification was produced at
    all. A report script should degrade to "this account unreadable" per
    account, never crash the whole run over one account's connectivity."""
    try:
        broker = make_broker()
        acct = broker.account()
        positions = sorted(broker.positions(), key=lambda p: -p.market_value)
        return AccountReport(label, acct.equity, acct.cash, positions)
    except (BrokerError, requests.exceptions.RequestException) as e:
        return AccountReport(label, 0.0, 0.0, [], error=str(e))


def collect() -> list[AccountReport]:
    return [
        _fetch("tae2", Tae2Broker.from_env),
        _fetch("stocks (MoVo10)", stocks_broker_from_env),
    ]


def _table(report: AccountReport, stock_names: dict[str, str]) -> list[str]:
    lines = [
        "| Simbol | Denumire completă | Cantitate | Valoare (\\$) | Pondere |",
        "|---|---|---:|---:|---:|",
    ]
    for p in report.positions:
        weight = p.market_value / report.equity if report.equity else 0.0
        name = resolve_name(p.symbol, stock_names)
        lines.append(f"| {p.symbol} | {name} | {p.qty:.3f} | {p.market_value:,.2f} | {weight:.1%} |")
    return lines


def to_markdown(reports: list[AccountReport], stock_names: dict[str, str], now: datetime) -> str:
    lines = [
        f"# Raport portofoliu — {now.date().isoformat()} {now.strftime('%H:%M')} UTC",
        "",
        "Doar citire — niciun ordin nu este trimis de acest raport.",
        "",
    ]
    total_equity = sum(r.equity for r in reports)
    lines += [f"**Total combinat:** \\${total_equity:,.2f}", ""]
    for r in reports:
        lines.append(f"## {r.label}")
        lines.append("")
        if r.error:
            lines.append(f"⚠️ Nu s-a putut citi contul: {r.error}")
            lines.append("")
            continue
        invested = r.equity - r.cash
        lines += [
            f"Echitate: **\\${r.equity:,.2f}**  ·  Cash: \\${r.cash:,.2f}  ·  Investit: \\${invested:,.2f}  ·  Poziții: {len(r.positions)}",
            "",
        ]
        if r.positions:
            lines += _table(r, stock_names)
        else:
            lines.append("_Nicio poziție deschisă._")
        lines.append("")
    return "\n".join(lines) + "\n"


def to_html(reports: list[AccountReport], stock_names: dict[str, str], now: datetime) -> str:
    total_equity = sum(r.equity for r in reports)
    parts = [
        "<!DOCTYPE html><html lang='ro'><head><meta charset='utf-8'>",
        f"<title>Raport portofoliu {now.date().isoformat()}</title>",
        "<style>",
        "body{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a;background:#fafafa}",
        "h1{font-size:1.4rem} h2{font-size:1.1rem;margin-top:2rem;border-bottom:2px solid #ddd;padding-bottom:.3rem}",
        "table{border-collapse:collapse;width:100%;font-size:.9rem;background:#fff}",
        "th,td{padding:.4rem .6rem;text-align:right;border-bottom:1px solid #eee}",
        "th:nth-child(1),td:nth-child(1),th:nth-child(2),td:nth-child(2){text-align:left}",
        "th{background:#f0f0f0} tr:hover{background:#f7f9fc}",
        ".summary{font-size:.95rem;color:#333;margin-bottom:.6rem}",
        ".total{font-size:1.2rem;font-weight:600;margin:.6rem 0 1.2rem}",
        ".err{color:#b00020}",
        "</style></head><body>",
        f"<h1>Raport portofoliu — {now.date().isoformat()} {now.strftime('%H:%M')} UTC</h1>",
        "<p><em>Doar citire — niciun ordin nu este trimis de acest raport.</em></p>",
        f"<div class='total'>Total combinat: ${total_equity:,.2f}</div>",
    ]
    for r in reports:
        parts.append(f"<h2>{r.label}</h2>")
        if r.error:
            parts.append(f"<p class='err'>⚠️ Nu s-a putut citi contul: {r.error}</p>")
            continue
        invested = r.equity - r.cash
        parts.append(
            f"<div class='summary'>Echitate: <b>${r.equity:,.2f}</b> &nbsp;·&nbsp; "
            f"Cash: ${r.cash:,.2f} &nbsp;·&nbsp; Investit: ${invested:,.2f} &nbsp;·&nbsp; "
            f"Poziții: {len(r.positions)}</div>"
        )
        if not r.positions:
            parts.append("<p><em>Nicio poziție deschisă.</em></p>")
            continue
        parts.append("<table><tr><th>Simbol</th><th>Denumire completă</th><th>Cantitate</th><th>Valoare ($)</th><th>Pondere</th></tr>")
        for p in r.positions:
            weight = p.market_value / r.equity if r.equity else 0.0
            name = resolve_name(p.symbol, stock_names)
            parts.append(
                f"<tr><td>{p.symbol}</td><td>{name}</td><td>{p.qty:.3f}</td>"
                f"<td>{p.market_value:,.2f}</td><td>{weight:.1%}</td></tr>"
            )
        parts.append("</table>")
    parts.append("</body></html>")
    return "\n".join(parts)


def notify(reports: list[AccountReport]) -> None:
    """A macOS notification with the headline numbers -- best-effort, never fails the report."""
    bits = []
    for r in reports:
        bits.append(f"{r.label}: eroare" if r.error else f"{r.label}: ${r.equity:,.0f}")
    msg = " | ".join(bits)
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{msg}" with title "Raport portofoliu"'],
            check=False,
            timeout=10,
        )
    except OSError:
        pass


def main() -> int:
    now = datetime.now(timezone.utc)
    reports = collect()
    stock_names = universe.load_names(refresh=False)
    md = to_markdown(reports, stock_names, now)
    html = to_html(reports, stock_names, now)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md_path = OUT_DIR / f"portfolio_report_{date.today().isoformat()}.md"
    html_path = OUT_DIR / f"portfolio_report_{date.today().isoformat()}.html"
    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html, encoding="utf-8")
    print(md)
    print(f"Report written to {md_path} and {html_path}")
    notify(reports)
    return 0 if all(r.error is None for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
