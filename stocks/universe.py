"""The stock universe this lab tests strategies on.

KNOWN LIMITATION, read before trusting any gate pass: this fetches TODAY's
S&P 500 members and uses that fixed list for the whole 2008-2026 backtest
window. Real point-in-time membership (which stocks were actually in the
index on each historical date) is not used -- constituents that were
removed (bankrupt, acquired, demoted) before today are invisible to the
backtest. This is survivorship bias, and it inflates every result below
until a point-in-time constituents dataset replaces this. Treat every
number here as a first-pass architecture check, not a gate-trustworthy
result, until that is fixed.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

CACHE = Path("data_cache/sp500_current_members.json")
WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
# Wikipedia returns 403 without a UA; this is a research script identifying itself, not spoofing a browser.
_HEADERS = {"User-Agent": "tae2-stocks-research (local backtest, non-commercial)"}


def fetch_current_members() -> list[str]:
    """Today's S&P 500 tickers from Wikipedia, in Yahoo Finance format (BRK.B -> BRK-B)."""
    resp = requests.get(WIKIPEDIA_URL, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    table = pd.read_html(io.StringIO(resp.text))[0]
    tickers = table["Symbol"].astype(str).str.strip().str.replace(".", "-", regex=False)
    return sorted(tickers.unique().tolist())


def load(refresh: bool = False) -> list[str]:
    """Cached ticker list; refetches from Wikipedia when asked or missing."""
    if not refresh and CACHE.is_file():
        return json.loads(CACHE.read_text(encoding="utf-8"))["tickers"]
    tickers = fetch_current_members()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(
        json.dumps(
            {
                "tickers": tickers,
                "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "source": WIKIPEDIA_URL,
                "count": len(tickers),
                "survivorship_bias_warning": (
                    "Current members only, not point-in-time. See this module's docstring."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return tickers
