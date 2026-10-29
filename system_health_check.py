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
3b. Heartbeat: did last evening's scheduled run really happen near its time
   (journal check, done BEFORE self-heal so a catch-up can't hide a miss)?
3c. Dry-plan the latest decision against the real positions and reject any
   order the broker would refuse (never sends anything).
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

import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from tae2 import data as tae2_data
from tae2 import engine as tae2_engine
from tae2 import rebalance as tae2_rebalance
from tae2.broker import AlpacaPaper as Tae2Broker
from tae2.broker import BrokerError
from stocks import data as stocks_data
from stocks import engine as stocks_engine
from stocks import rebalance as stocks_rebalance
from stocks.broker import from_env as stocks_broker_from_env

OUT_DIR = Path("output")
NON_BLOCKING_ISSUE_KINDS = {"JUMP"}  # same tolerance tae2/engine.py's own blocking filter uses

# Added 2026-10-29 after three things this check said "OK" to while being wrong:
# - the Mac slept 36h and the 10-28 evening jobs never ran (nothing reported it),
# - 22 sub-$1 share remainders would have made the 11-02 rebalance send qty-0
#   sells that Alpaca rejects (nothing simulated the next rebalance),
# - "529 JUMP tolerate" every day was history, not news.
BUCHAREST = ZoneInfo("Europe/Bucharest")
HEARTBEAT_EARLY = timedelta(minutes=10)  # a scheduled run counts if journaled within this window
HEARTBEAT_LATE = timedelta(minutes=90)  # around its launchd time (21:30 tae2, 21:40 stocks)
RECENT_JUMP_DAYS = 7  # ~5 sessions: older jumps are history, not news


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
    # sys.executable, NOT a bare "python3": launchd starts with a minimal
    # PATH (same note tae2/engine.py's own deploy scripts already carry),
    # where plain "python3" resolves to macOS's own system Python (3.9,
    # no pandas) instead of this project's venv -- found 2026-10-12 when
    # the real health-check run reported 14/14 tests "failed" (every test
    # file that imports pandas/yfinance errored on import under that wrong
    # interpreter). sys.executable is whatever interpreter is ALREADY
    # running this script, which run_health_check.sh already resolved
    # correctly before launching it.
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        capture_output=True, text=True, timeout=300,
    )
    ok = proc.returncode == 0
    tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
    return CheckResult("Teste", ok, "OK" if ok else "; ".join(tail))


def check_data(label: str, load, split=None, now: datetime | None = None) -> tuple[CheckResult, object]:
    """`load` is a (refresh=True) -> (prices, issues) callable, same contract
    tae2.data.load/stocks.data.load already share. `split` (stocks only) is the
    engine's own issues -> (blocking, excluded) policy, so this check agrees with
    what the engine will actually do."""
    now = now or datetime.now(timezone.utc)
    try:
        prices, issues = load(refresh=True)
    except Exception as e:  # yfinance/network failures surface here, not a crash
        return CheckResult(f"Date {label}", False, f"eroare la descărcare: {e}"), None
    if split is not None:
        blocking, excluded = split(issues)
    else:
        blocking, excluded = [i for i in issues if i.kind not in NON_BLOCKING_ISSUE_KINDS], []
    if blocking:
        detail = "; ".join(f"{i.ticker} {i.kind}: {i.detail}" for i in blocking)
        return CheckResult(f"Date {label}", False, detail), prices
    # Issue.detail for a JUMP starts with its ISO date ("2026-10-20 moved 28%").
    cutoff = (now - timedelta(days=RECENT_JUMP_DAYS)).date().isoformat()
    recent = sorted({i.ticker for i in issues if i.kind in NON_BLOCKING_ISSUE_KINDS and i.detail[:10] >= cutoff})
    notes = []
    if excluded:
        notes.append(f"{len(excluded)} ticker(e) excluse din rulare: {', '.join(excluded)}")
    if recent:
        shown = ", ".join(recent[:8]) + (f" +{len(recent) - 8}" if len(recent) > 8 else "")
        notes.append(f"{len(recent)} ticker(e) cu mișcări >25% în ultimele {RECENT_JUMP_DAYS} zile: {shown}")
    detail = "OK" if not notes else f"OK ({'; '.join(notes)})"
    return CheckResult(f"Date {label}", True, detail), prices


def check_broker(label: str, make_broker) -> CheckResult:
    try:
        acct = make_broker().account()
    except (BrokerError, requests.exceptions.RequestException) as e:
        return CheckResult(f"Cont {label}", False, f"inaccesibil: {e}")
    if acct.trading_blocked:
        return CheckResult(f"Cont {label}", False, "trading_blocked=true pe cont")
    return CheckResult(f"Cont {label}", True, f"OK, echitate ${acct.equity:,.2f}")


def last_expected_run(now: datetime, hour: int, minute: int) -> datetime:
    """The most recent weekday launchd run (hour:minute Bucharest) whose window has fully passed."""
    local = now.astimezone(BUCHAREST)
    day = local.date()
    while True:
        candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=BUCHAREST)
        if day.weekday() < 5 and candidate + HEARTBEAT_LATE <= local:
            return candidate
        day -= timedelta(days=1)


def check_heartbeat(label: str, journal: Path, hour: int, minute: int, now: datetime) -> CheckResult:
    """Did last evening's scheduled run actually happen, near its time? The self-heal
    below would silently catch up a missed run, hiding that the Mac slept through it
    (2026-10-28), so this looks at the journal *before* self-heal writes anything."""
    name = f"Rulare programată {label}"
    expected = last_expected_run(now, hour, minute)
    when = f"{expected:%a %d.%m %H:%M}"
    try:
        entries = [datetime.fromisoformat(json.loads(line)["at"]) for line in journal.read_text().splitlines() if line.strip()]
    except OSError:
        return CheckResult(name, False, f"jurnal lipsă ({journal}); rularea de {when} nu poate fi confirmată")
    in_window = [t for t in entries if expected - HEARTBEAT_EARLY <= t <= expected + HEARTBEAT_LATE]
    if in_window:
        ran = min(in_window).astimezone(BUCHAREST)
        return CheckResult(name, True, f"OK: {when} → rulată la {ran:%H:%M}")
    after = [t for t in entries if t > expected + HEARTBEAT_LATE]
    if after:
        first = min(after)
        late = f"prima rulare de după: {first.astimezone(BUCHAREST):%a %d.%m %H:%M} (întârziere {(first - expected).total_seconds() / 3600:.1f} h)"
    else:
        late = "nicio rulare de atunci"
    return CheckResult(name, False, f"NU a rulat în jurul orei {when} (Mac adormit sau job picat); {late}")


def check_plan(label: str, strategy: str, engine_module, rebalance_module, make_broker, prices, now: datetime,
               excluded=()) -> CheckResult:
    """Dry-plan the latest decision against the REAL positions and reject any order the
    broker would refuse, so a rebalance that would abort is found days ahead, not at 21:40.
    Never sends anything. (2026-10-29: would have caught qty-0.000000 exit sells for the
    sub-$1 remainders that floored exits leave behind.)"""
    name = f"Plan rebalansare {label}"
    try:
        if len(excluded):
            prices = prices.drop(columns=list(excluded))
        decision = tae2_engine.latest_decision(prices, now)
        targets = engine_module.targets_for(strategy, prices, decision)
        broker = make_broker()
        acct = broker.account()
        positions = broker.positions()
        orders = rebalance_module.plan(targets, positions, acct.equity, acct.cash)
    except Exception as e:
        return CheckResult(name, False, f"simularea a eșuat: {e}")
    held = {p.symbol: p.qty for p in positions}
    bad = []
    for o in orders:
        if o.side == "sell":
            sent = math.floor(o.qty * 1_000_000) / 1_000_000  # what AlpacaPaper.submit actually sends
            if sent <= 0 or o.qty > held.get(o.symbol, 0.0) + 1e-9:
                bad.append(f"{o.symbol} vânzare qty {o.qty:.3g} (se trimite {sent:.6f}, deținut {held.get(o.symbol, 0.0):.6g})")
        elif o.notional is None or round(o.notional, 2) < 1.0:
            bad.append(f"{o.symbol} cumpărare ${o.notional} sub minimul de $1")
    if bad:
        shown = "; ".join(bad[:5]) + (f" (+{len(bad) - 5})" if len(bad) > 5 else "")
        return CheckResult(name, False, f"{len(bad)} din {len(orders)} ordine ar fi respinse de broker: {shown}")
    sells = sum(1 for o in orders if o.side == "sell")
    return CheckResult(name, True, f"OK: {len(orders)} ordine ipotetice, toate valide ({sells} vânzări, {len(orders) - sells} cumpărări)")


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

    tae2_check, tae2_prices = check_data("tae2 (ETF-uri)", tae2_data.load, now=now)
    report.checks.append(tae2_check)
    stocks_check, stocks_prices = check_data(
        "stocks (S&P 500)", stocks_data.load, split=stocks_data.split_issues, now=now
    )
    report.checks.append(stocks_check)

    report.checks.append(check_broker("tae2", Tae2Broker.from_env))
    report.checks.append(check_broker("stocks (MoVo10)", stocks_broker_from_env))

    # Before self-heal, which writes journal entries of its own.
    report.checks.append(check_heartbeat("tae2", tae2_engine.JOURNAL, 21, 30, now))
    report.checks.append(check_heartbeat("stocks", stocks_engine.JOURNAL, 21, 40, now))

    if tae2_check.ok and tae2_prices is not None:
        report.checks.append(
            check_plan("tae2", tae2_engine.DEFAULT_STRATEGY, tae2_engine, tae2_rebalance, Tae2Broker.from_env,
                       tae2_prices, now)
        )
    if stocks_check.ok and stocks_prices is not None:
        _, stocks_excluded = stocks_data.split_issues(stocks_data.validate(stocks_prices, now))
        report.checks.append(
            check_plan("stocks", stocks_engine.DEFAULT_STRATEGY, stocks_engine, stocks_rebalance,
                       stocks_broker_from_env, stocks_prices, now, excluded=stocks_excluded)
        )

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
