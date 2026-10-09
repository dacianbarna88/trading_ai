"""Daily system health check, run every weekday morning BEFORE markets open
(deploy/run_health_check.sh + deploy/com.health.check.plist), requested
2026-10-09: "un job care sa verifice sanatatea sistemului, daca exista
probleme sa se poata identifica si repara... inainte de deschiderea
pietelor" (a job that checks system health and identifies/repairs problems
before markets open).

Checks, in order:
1. Test suite (`python -m unittest discover`) -- cannot be auto-fixed if it
   fails (a real code regression needs a human); surfaced, never guessed at.
2. Price-data validation for tae2's and the stocks lab's universes, reusing
   tae2.data.validate()/stocks.data.validate() completely unchanged. Only
   GAP/STALE/NON_POSITIVE/PARTIAL_BAR issues block (same convention
   tae2/engine.py's own `blocking = [i for i in issues if i.kind != "JUMP"]`
   already uses) -- a single large JUMP isn't necessarily bad data.
3. Both Alpaca paper accounts reachable (.account() on each).
4. SELF-HEAL, not a separate invented "fix": re-runs tae2's and the stocks
   lab's own `engine.run(..., submit=True)` -- the EXACT command the
   21:30/21:40 evening jobs already run. This is safe to call any number
   of times by the engine's own design ("each decision executed at most
   once... running daily is safe and a missed day catches up on the next
   run" -- tae2/engine.py's own docstring). If last evening's run silently
   failed (the exact failure already seen once in this project: a
   transient yfinance outage), this catches it up before today's open
   instead of waiting for tonight. Nothing new or risky is introduced --
   it is the same idempotent, paper-only call, just made an extra time.

What this CANNOT fix, and never pretends to: failing tests, broker auth
failures, genuine data corruption, a real code bug. Those are surfaced in
the report and via a macOS notification -- there is no other alert channel,
so if the notification is missed, check output/system_health_*.md by hand.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from tae2 import data as tae2_data
from tae2 import engine as tae2_engine
from tae2.broker import AlpacaPaper as Tae2Broker
from tae2.broker import BrokerError
from stocks import data as stocks_data
from stocks import engine as stocks_engine
from stocks.broker import from_env as stocks_broker_from_env

OUT_DIR = Path("output")
NON_BLOCKING_ISSUE_KINDS = {"JUMP"}  # same tolerance tae2/engine.py's own blocking filter uses


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


@dataclass
class HealthReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append(CheckResult(name, ok, detail))


def run_tests() -> CheckResult:
    proc = subprocess.run(
        ["python3", "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        capture_output=True, text=True, timeout=300,
    )
    ok = proc.returncode == 0
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
    return CheckResult("Teste", ok, "OK" if ok else "; ".join(tail))


def check_data(label: str, load) -> tuple[CheckResult, object]:
    """`load` is a (refresh=True) -> (prices, issues) callable, same contract
    tae2.data.load/stocks.data.load already share."""
    try:
        prices, issues = load(refresh=True)
    except Exception as e:  # yfinance/network failures surface here, not a crash
        return CheckResult(f"Date {label}", False, f"eroare la descărcare: {e}"), None
    blocking = [i for i in issues if i.kind not in NON_BLOCKING_ISSUE_KINDS]
    if blocking:
        detail = "; ".join(f"{i.ticker} {i.kind}: {i.detail}" for i in blocking)
        return CheckResult(f"Date {label}", False, detail), prices
    tolerated = len(issues)
    detail = "OK" if not tolerated else f"OK ({tolerated} JUMP tolerate, verifică dacă persistă)"
    return CheckResult(f"Date {label}", True, detail), prices


def check_broker(label: str, make_broker) -> CheckResult:
    try:
        acct = make_broker().account()
    except (BrokerError, requests.exceptions.RequestException) as e:
        return CheckResult(f"Cont {label}", False, f"inaccesibil: {e}")
    if acct.trading_blocked:
        return CheckResult(f"Cont {label}", False, "trading_blocked=true pe cont")
    return CheckResult(f"Cont {label}", True, f"OK, echitate ${acct.equity:,.2f}")


def self_heal(label: str, strategy: str, module, prices, now: datetime) -> CheckResult:
    """Re-runs the exact command the evening job already runs. Idempotent
    by the engine's own design -- "already_done" most days, a real catch-up
    on the rare day the evening run didn't complete."""
    try:
        report = module.run(strategy, submit=True, prices=prices, now=now)
    except Exception as e:
        return CheckResult(f"Motor {label}", False, f"eroare la rulare: {e}")
    ok = report.status in {"already_done", "submitted", "dry_run"}
    return CheckResult(f"Motor {label}", ok, f"{report.status}: {report.detail or report.decision_date}")


def collect(now: datetime | None = None) -> HealthReport:
    now = now or datetime.now(timezone.utc)
    report = HealthReport()

    t = run_tests()
    report.checks.append(t)

    tae2_check, tae2_prices = check_data("tae2 (ETF-uri)", tae2_data.load)
    report.checks.append(tae2_check)
    stocks_check, stocks_prices = check_data("stocks (S&P 500)", stocks_data.load)
    report.checks.append(stocks_check)

    report.checks.append(check_broker("tae2", Tae2Broker.from_env))
    report.checks.append(check_broker("stocks (MoVo10)", stocks_broker_from_env))

    if tae2_check.ok and tae2_prices is not None:
        report.checks.append(self_heal("tae2", tae2_engine.DEFAULT_STRATEGY, tae2_engine, tae2_prices, now))
    if stocks_check.ok and stocks_prices is not None:
        report.checks.append(self_heal("stocks", stocks_engine.DEFAULT_STRATEGY, stocks_engine, stocks_prices, now))

    return report


def to_markdown(report: HealthReport, now: datetime) -> str:
    lines = [
        f"# Verificare sănătate sistem — {now.date().isoformat()} {now.strftime('%H:%M')} UTC",
        "",
        "Rulează în fiecare zi lucrătoare, înainte de deschiderea piețelor. Reîncearcă automat "
        "(idempotent, sigur) orice rebalansare ratată aseară; NU poate repara teste căzute, "
        "chei broker greșite sau date real corupte -- acelea sunt semnalate, nu ghicite.",
        "",
    ]
    for c in report.checks:
        lines.append(f"- {'✓' if c.ok else '✗ PROBLEMĂ'} {c.name}: {c.detail}")
    lines += ["", f"**Verdict: {'TOTUL OK' if report.ok else 'NECESITĂ ATENȚIE ÎNAINTE DE DESCHIDERE'}**", ""]
    return "\n".join(lines) + "\n"


def notify(report: HealthReport) -> None:
    title = "Verificare sistem: OK" if report.ok else "⚠️ Verificare sistem: PROBLEMĂ"
    bad = [c.name for c in report.checks if not c.ok]
    msg = "Totul e în regulă." if report.ok else f"Probleme: {', '.join(bad)}"
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{msg}" with title "{title}"'],
            check=False, timeout=10,
        )
    except OSError:
        pass


def write_report(text: str, out_dir: Path = OUT_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"system_health_{date.today().isoformat()}.md"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    now = datetime.now(timezone.utc)
    report = collect(now)
    text = to_markdown(report, now)
    print(text)
    path = write_report(text)
    print(f"Report written to {path}")
    notify(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
