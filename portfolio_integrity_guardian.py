"""
Portfolio Integrity Guardian — structural sanity checks on portfolio.csv.

PAPER_ONLY | NO_BROKER | NO_EXECUTION | NO_PORTFOLIO_CHANGE

Detects the class of silent data-corruption bug found repeatedly during
this codebase's audit: a bad write leaving portfolio.csv with rows that
violate its own invariants (a SELL for more shares than are actually
held, a negative price, a malformed Action) long before anyone notices
from wrong P&L. Read-only: never modifies portfolio.csv. Sends a
Telegram alert only when a CRITICAL finding exists.
"""

from pathlib import Path

import pandas as pd

from utils.logger import log
from utils.telegram import send_telegram

VALID_ACTIONS = {"BUY", "SELL", "DEPOSIT"}
REQUIRED_COLUMNS = ["Date", "Ticker", "Action", "Price", "Shares"]

REPORT_FILE = "portfolio_integrity_report.csv"
SUMMARY_FILE = "portfolio_integrity_summary.txt"


def check_portfolio_integrity(df: pd.DataFrame) -> list[dict]:
    """Return a list of {row, ticker, severity, issue} findings. Read-only."""
    findings: list[dict] = []

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        findings.append(
            {
                "row": "",
                "ticker": "",
                "severity": "CRITICAL",
                "issue": f"Missing required column(s): {', '.join(missing_cols)}",
            }
        )
        return findings

    df = df.copy()
    df["Ticker_isna"] = df["Ticker"].isna()
    df["Price_num"] = pd.to_numeric(df["Price"], errors="coerce")
    df["Shares_num"] = pd.to_numeric(df["Shares"], errors="coerce")
    df["Action_upper"] = df["Action"].astype(str).str.upper().str.strip()
    df["Ticker_upper"] = df["Ticker"].astype(str).str.upper().str.strip()

    open_shares: dict[str, float] = {}

    for idx, row in df.iterrows():
        ticker = row["Ticker_upper"]
        action = row["Action_upper"]
        price = row["Price_num"]
        shares = row["Shares_num"]

        if row["Ticker_isna"] or not ticker:
            findings.append({"row": idx, "ticker": ticker, "severity": "CRITICAL", "issue": "Missing Ticker"})
            continue

        if action not in VALID_ACTIONS:
            findings.append(
                {"row": idx, "ticker": ticker, "severity": "CRITICAL", "issue": f"Invalid Action: {row['Action']!r}"}
            )
            continue

        if ticker == "CASH":
            # CASH marker rows (if any) carry no share-count invariant.
            continue

        if pd.isna(price) or price <= 0:
            findings.append(
                {"row": idx, "ticker": ticker, "severity": "CRITICAL", "issue": f"Non-positive Price: {row['Price']!r}"}
            )

        if pd.isna(shares) or shares <= 0:
            findings.append(
                {"row": idx, "ticker": ticker, "severity": "CRITICAL", "issue": f"Non-positive Shares: {row['Shares']!r}"}
            )
            continue

        if action == "BUY":
            open_shares[ticker] = open_shares.get(ticker, 0.0) + shares

        elif action == "SELL":
            held = open_shares.get(ticker, 0.0)
            if held <= 0:
                findings.append(
                    {
                        "row": idx,
                        "ticker": ticker,
                        "severity": "CRITICAL",
                        "issue": f"SELL with no open position (orphaned SELL, {shares} shares)",
                    }
                )
            elif shares > held + 1e-6:
                findings.append(
                    {
                        "row": idx,
                        "ticker": ticker,
                        "severity": "CRITICAL",
                        "issue": f"SELL for {shares} shares exceeds open position of {held} shares",
                    }
                )
            # SELLs in this system always fully liquidate the current
            # holding, regardless of the share count on the row itself.
            open_shares[ticker] = 0.0

    return findings


def _write_report(findings: list[dict]) -> pd.DataFrame:
    report_df = pd.DataFrame(findings, columns=["row", "ticker", "severity", "issue"])
    report_df.to_csv(REPORT_FILE, index=False)
    return report_df


def _build_summary(findings: list[dict]) -> str:
    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    lines = [
        "===== PORTFOLIO INTEGRITY GUARDIAN =====",
        "",
        f"Findings: {len(findings)} ({len(critical)} CRITICAL)",
        "",
    ]
    if findings:
        for f in findings:
            lines.append(f"row={f['row']} ticker={f['ticker']} [{f['severity']}] {f['issue']}")
    else:
        lines.append("No integrity issues found in portfolio.csv.")
    lines.extend(
        [
            "",
            "Status:",
            "PAPER_ONLY",
            "NO_BROKER",
            "NO_EXECUTION",
            "NO_PORTFOLIO_CHANGE",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    portfolio_file = Path("portfolio.csv")

    if not portfolio_file.exists():
        log("Portfolio Integrity Guardian: portfolio.csv not found — nothing to check.")
        return 0

    df = pd.read_csv(portfolio_file)
    findings = check_portfolio_integrity(df)

    _write_report(findings)
    summary = _build_summary(findings)
    Path(SUMMARY_FILE).write_text(summary, encoding="utf-8")

    print(summary)
    log(f"Portfolio Integrity Guardian: {len(findings)} finding(s).")

    critical = [f for f in findings if f["severity"] == "CRITICAL"]
    if critical:
        alert_lines = "\n".join(f"- {f['ticker']}: {f['issue']}" for f in critical[:10])
        send_telegram(
            f"🚨 Portfolio Integrity Guardian: {len(critical)} CRITICAL finding(s) in portfolio.csv\n{alert_lines}"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
