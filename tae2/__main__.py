"""Command line: `python -m tae2 research [--refresh] [--allow-data-issues]`."""

from __future__ import annotations

import argparse
import sys

from tae2 import data, research


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tae2")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("research", help="walk-forward test of every candidate against the gates")
    r.add_argument("--refresh", action="store_true", help="download prices again instead of using the cache")
    r.add_argument(
        "--allow-data-issues",
        action="store_true",
        help="run even when validation reports problems (they are listed in the report)",
    )
    args = parser.parse_args(argv)

    prices, issues = data.load(refresh=args.refresh)
    blocking = [i for i in issues if i.kind != "JUMP"]
    if blocking and not args.allow_data_issues:
        for i in blocking:
            print(f"DATA {i.kind} {i.ticker}: {i.detail}", file=sys.stderr)
        print("Stopped: fix the data (try --refresh) or pass --allow-data-issues.", file=sys.stderr)
        return 2
    rows, n_trials = research.run(prices)
    text = research.to_markdown(rows, n_trials, issues, prices)
    path = research.write_report(text)
    print(text)
    print(f"Report written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
