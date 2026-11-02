"""Morning / evening status, one command: budget, portfolio, positions, last runs.

    python3 status_notify.py morning     # after the 10:20 health check
    python3 status_notify.py evening     # after the 23:30 portfolio report
    python3 status_notify.py evening --no-notify   # just print + write the file

Read-only: reads both Alpaca paper accounts (account/positions/portfolio
history, never an order) and the engines' run journals. Sends a short macOS
notification and writes the full text to output/status_<kind>_<date>.md,
which the cloud routines read to push the same numbers to the phone.

Replaces the two older one-line banners (equity only / "TOTUL OK" only): the
2026-10-30 -> 11-02 review found nobody saw them, and neither said how much
cash, how many positions, or whether tonight's run actually traded.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import portfolio_report as pr
from stocks import engine as stocks_engine
from tae2 import engine as tae2_engine

BUCHAREST = ZoneInfo("Europe/Bucharest")
OUT_DIR = Path("output")
TOP_N = 5


@dataclass
class Summary:
    title: str
    short: str  # macOS notification body
    long: str  # markdown, written to output/


def _pct(x: float) -> str:
    return f"{100 * x:+.2f}%"


def _changes(r: pr.AccountReport) -> tuple[float | None, float | None]:
    """(last day, since inception) from Alpaca's own daily equity curve."""
    h = r.history
    if len(h) < 2:
        return None, None
    return h[-1].equity / h[-2].equity - 1, h[-1].equity / h[0].equity - 1


def _runs_today(journal: Path, today: date) -> list[dict]:
    """The engine's journal entries written today (Bucharest time), oldest first."""
    try:
        lines = journal.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            entry = json.loads(line)
            at = datetime.fromisoformat(entry["at"]).astimezone(BUCHAREST)
        except (ValueError, KeyError):
            continue
        if at.date() == today:
            entry["_at"] = at
            out.append(entry)
    return out


def _runs_text(runs: list[dict]) -> str:
    if not runs:
        return "nicio rulare azi"
    traded = [e for e in runs if e.get("status") == "submitted"]
    if traded:
        orders = sum(len(e.get("orders") or []) for e in traded)
        return f"{orders} ordine trimise la {traded[-1]['_at']:%H:%M} (decizia {traded[-1].get('decision_date')})"
    last = runs[-1]
    return f"{last.get('status')} la {last['_at']:%H:%M}"


def _health(day: date, out_dir: Path) -> tuple[str, list[str]]:
    """(verdict, lines marked ✗) from today's morning health report."""
    path = out_dir / f"system_health_{day.isoformat()}.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "raportul de sănătate de azi lipsește", []
    verdict = re.search(r"\*\*Verdict: (.+?)\*\*", text)
    bad = [line.lstrip("- ").strip() for line in text.splitlines() if "✗" in line]
    return (verdict.group(1) if verdict else "verdict necunoscut"), bad


def build(
    reports: list[pr.AccountReport],
    kind: str,
    now: datetime,
    journals: dict[str, Path],
    out_dir: Path = OUT_DIR,
) -> Summary:
    local = now.astimezone(BUCHAREST)
    day = local.date()
    label_kind = "dimineață" if kind == "morning" else "seară"
    long = [f"# Status {label_kind} — {local:%Y-%m-%d %H:%M}", ""]
    short = []

    problems: list[str] = []
    if kind == "morning":
        verdict, problems = _health(day, out_dir)
        long += [f"**Verificare sistem:** {verdict}", ""]
        long += [f"- ✗ {p.replace('✗ ', '')}" for p in problems] + ([""] if problems else [])

    total = 0.0
    for r in reports:
        nick = "MoVo10" if r.label.startswith("stocks") else r.label
        if r.error:
            long += [f"## {r.label}", f"⚠️ Cont necitit: {r.error}", ""]
            short.append(f"{nick}: eroare")
            problems.append(f"{r.label} necitit")
            continue
        total += r.equity
        day_chg, total_chg = _changes(r)
        invested = sum(p.market_value for p in r.positions)
        runs = _runs_text(_runs_today(journals[r.label], day))
        long += [
            f"## {r.label}",
            f"- Echitate: **${r.equity:,.2f}**  ·  Cash (buget liber): ${r.cash:,.2f}  ·  Investit: ${invested:,.2f}",
            f"- Poziții: **{len(r.positions)}**{pr._dust_note(r)}",
            f"- Variație ultima zi: {_pct(day_chg) if day_chg is not None else 'n/a'}  ·  "
            f"de la pornire: {_pct(total_chg) if total_chg is not None else 'n/a'}",
            f"- Ultima rulare de azi: {runs}",
            "",
        ]
        if r.positions:
            long.append(f"Top {min(TOP_N, len(r.positions))} poziții:")
            for p in r.positions[:TOP_N]:
                weight = p.market_value / r.equity if r.equity else 0.0
                long.append(f"- {p.symbol}: ${p.market_value:,.0f} ({100 * weight:.1f}%, {_pct(p.change_pct)} față de intrare)")
            long.append("")
        extra = f", {_pct(day_chg)} ieri" if day_chg is not None else ""
        short.append(f"{nick} ${r.equity:,.0f} (cash ${r.cash:,.0f}, {len(r.positions)} poz{extra})")

    long.insert(2, f"**Total combinat: ${total:,.2f}**")
    long.insert(3, "")
    flag = "⚠️ " if problems else ""
    title = f"{flag}Status {label_kind}"
    msg = " | ".join(short)
    if kind == "morning":
        msg += " | sistem OK" if not problems else f" | {len(problems)} probleme"
    return Summary(title, msg, "\n".join(long))


def _notify(title: str, msg: str) -> None:
    """macOS banner -- best effort, never fails the run."""
    safe = lambda s: s.replace("\\", " ").replace('"', "'")
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{safe(msg)}" with title "{safe(title)}"'],
            check=False, timeout=10,
        )
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("kind", choices=["morning", "evening"])
    ap.add_argument("--no-notify", action="store_true", help="print and write the file only")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    reports = pr.collect()
    journals = {"tae2": tae2_engine.JOURNAL, "stocks (MoVo10)": stocks_engine.JOURNAL}
    summary = build(reports, args.kind, now, journals)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"status_{args.kind}_{now.astimezone(BUCHAREST).date().isoformat()}.md"
    path.write_text(summary.long + "\n", encoding="utf-8")
    print(summary.long)
    print(f"Status written to {path}")
    if not args.no_notify:
        _notify(summary.title, summary.short)
    return 0 if all(r.error is None for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
