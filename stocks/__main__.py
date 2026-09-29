"""Command line.

python -m stocks research [--refresh] [--allow-data-issues]
python -m stocks rebalance [--strategy momentum_vt10] [--submit]

"rebalance" trades on the stocks lab's OWN separate Alpaca paper account
("MoVo10", keys STOCKS_ALPACA_API_KEY_ID/STOCKS_ALPACA_API_SECRET_KEY) --
never tae2's. Without --submit nothing is sent, only shown (dry run).
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from stocks import data, engine, research, universe
from stocks.broker import load_dotenv


def main(argv: list[str] | None = None) -> int:
    import argparse

    load_dotenv()  # .env may set the STOCKS_ALPACA_* paper keys
    parser = argparse.ArgumentParser(prog="python -m stocks")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("research", help="walk-forward test of every candidate against the gates")
    r.add_argument("--refresh", action="store_true", help="download prices and the ticker list again instead of using the cache")
    r.add_argument(
        "--allow-data-issues",
        action="store_true",
        help="run even when validation reports problems (they are listed in the report)",
    )
    e = sub.add_parser("rebalance", help="bring the stocks lab's Alpaca paper account to the strategy's latest targets")
    e.add_argument("--strategy", default=engine.DEFAULT_STRATEGY, choices=sorted(engine.DEPLOYABLE))
    e.add_argument("--submit", action="store_true", help="send the orders (paper only); without it, only show them")
    args = parser.parse_args(argv)

    if args.command == "rebalance":
        report = engine.run(args.strategy, submit=args.submit)
        print(json.dumps(asdict(report), indent=2))
        return 0 if report.status in {"dry_run", "submitted", "already_done"} else 3

    prices, issues = data.load(refresh=args.refresh)
    blocking = [i for i in issues if i.kind != "JUMP"]
    if blocking and not args.allow_data_issues:
        for i in blocking:
            print(f"DATA {i.kind} {i.ticker}: {i.detail}", file=sys.stderr)
        print("Stopped: fix the data (try --refresh) or pass --allow-data-issues.", file=sys.stderr)
        return 2
    # The 503 S&P 500 companies only -- SPY (calendar/benchmark) and SHY
    # (cash proxy) are in `prices` for those roles but are not stock-picks.
    tickers = [t for t in universe.load(refresh=False) if t in prices.columns]
    rows, n_trials = research.run(prices, tickers)
    text = research.to_markdown(rows, n_trials, issues, prices, len(tickers))
    path = research.write_report(text)
    print(text)
    print(f"Report written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
