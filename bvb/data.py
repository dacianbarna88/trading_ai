"""Price data for the BVB (Bucharest Stock Exchange) research lab.

Every ticker below was checked for real yfinance history on 2026-10-08.
Suffix ".RO" is yfinance's own convention for BVB-listed names; the output
frame drops it (columns are plain "SNP", "TLV", etc.) to match how tae2/
the stocks lab name their own columns.

| Ticker | Company                          | Real history starts |
|--------|-----------------------------------|----------------------|
| SNP    | OMV Petrom                         | 2001-09-04 (25.1y)   |
| BRD    | BRD-Groupe Societe Generale        | 2001-01-18 (25.7y)   |
| ALR    | Alro                                | 2000-01-05 (26.8y)   |
| TLV    | Banca Transilvania                  | 2007-12-21 (18.8y)   |
| ATB    | Antibiotice                         | 2007-12-21 (18.8y)   |
| TGN    | Transgaz                            | 2008-01-25 (18.7y)   |
| EVER   | Evergent Investments                | 2008-02-20 (18.6y)   |
| TRANSI | Transilvania Investments Alliance   | 2008-02-20 (18.6y)   |
| FP     | Fondul Proprietatea                 | 2010-09-30 (16.0y)   |
| BVB    | Bursa de Valori Bucuresti (operator) | 2010-06-08 (16.3y)   |
| COTE   | Conpet                              | 2013-09-05 (13.1y)   |
| SNG    | Romgaz                              | 2013-11-12 (12.9y)   |
| SNN    | Nuclearelectrica                    | 2013-11-04 (12.9y)   |
| DIGI   | Digi Communications                  | 2017-05-23 (9.4y)    |
| SFG    | Sphera Franchise Group               | 2017-11-15 (9.0y)    |
| WINE   | Purcari Wineries                     | 2018-02-15 (8.7y)    |
| EL     | Electrica                           | 2018-05-30 (8.4y)    |
| ONE    | One United Properties                | 2021-07-12 (5.3y)    |
| TTS    | TTS (Transport Trade Services)        | 2021-06-18 (5.3y)    |
| AQ     | Aquila Part Prod Com                 | 2021-12-07 (4.9y)    |
| H2O    | Hidroelectrica                      | 2023-07-25 (3.2y)    |
| JTG    | JT Grup Oil                          | 2024-08-16 (2.2y)    |

Added 2026-10-08: JTG, specifically because it's one of Dacian's real
bt-trade.ro holdings (see the screenshot that prompted this package) --
momentum-universe only, its 2.2y is far short of the 15y trend-sleeve bar.

LONG_HISTORY (>=15 real years, used for the trend sleeve's 15-year gate):
SNP, BRD, ALR, TLV, ATB, TGN, EVER, TRANSI, FP, BVB -- 10 names.

One borderline case left UNPATCHED (below the <50% heuristic JUMP_DATES
uses, and the level shift doesn't revert): SNN +27% on 2018-12-21. Could be
a real single-day rally on a thin, mostly-state-owned float, or an
uncorrected action -- not verified either way, flagged here rather than
guessed at.

Everything above is used for the momentum ranking (data.UNIVERSE); momentum
only needs `top_n` names simultaneously valid on a given date (see
stocks.strategies.momentum), so the short-history names can still
contribute once they exist, without faking history they don't have.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE = Path("data_cache/bvb_prices.parquet")
DATA_START = "1999-01-01"
CASH = "CASH"  # literal 0% column -- see package docstring for why

RAW_TICKERS = [
    "SNP.RO", "BRD.RO", "ALR.RO", "TLV.RO", "ATB.RO", "TGN.RO", "EVER.RO",
    "TRANSI.RO", "FP.RO", "BVB.RO", "COTE.RO", "SNG.RO", "SNN.RO", "DIGI.RO",
    "SFG.RO", "WINE.RO", "EL.RO", "ONE.RO", "TTS.RO", "AQ.RO", "H2O.RO", "JTG.RO",
]
UNIVERSE = [t.removesuffix(".RO") for t in RAW_TICKERS]
LONG_HISTORY = ["SNP", "BRD", "ALR", "TLV", "ATB", "TGN", "EVER", "TRANSI", "FP", "BVB"]

# Found 2026-10-08 via tae2.data.validate()'s own JUMP detector: each date
# below is ONE day whose raw yfinance price is not a real market move --
# confirmed per-ticker by inspecting the surrounding prices:
#   - SNP 2005-07-04, BRD 2005-05-27/2005-08-02, ALR 2005-07-04: Romania's
#     real 2005-07-01 currency redenomination (10,000 old ROL = 1 new RON)
#     -- yfinance's history for these three wasn't rescaled across it.
#   - ALR 2000-09-25/2001-05-15/2001-10-04/2001-12-18/2002-10-30, BRD
#     2002-03-21/2003-02-20, TLV 2009-01-07, EVER/TRANSI 2010-02-12, FP
#     2011-01-25/2023-09-07, COTE 2016-06-13: a PERMANENT level shift
#     (inspected before/after) -- an uncorrected split, bonus issue or
#     similar corporate action; exact ratios not independently verified.
#   - FP 2017-12-26+12-27, TTS 2024-08-16+08-19: a single bad print that
#     fully reverts the next session -- a pure data-vendor glitch.
# The fix is the same for all three causes and needs no split ratio: the
# return INTO and OUT OF a flagged day is internally consistent on each
# side, only the one connecting day's return is fabricated. Zeroing just
# that day's return (not touching any other day) removes the artifact
# while leaving both the before- and after-segments' real relative moves
# untouched -- the same splice principle tae2_ucits/data.py uses for DBC.
JUMP_DATES: dict[str, list[str]] = {
    "SNP": ["2005-07-04"],
    "BRD": ["2002-03-21", "2003-02-20", "2005-05-27", "2005-08-02"],
    "ALR": ["2000-09-25", "2001-05-15", "2001-10-04", "2001-12-18", "2002-10-30", "2005-07-04"],
    "TLV": ["2009-01-07"],
    "EVER": ["2010-02-12"],
    "TRANSI": ["2010-02-12"],
    "FP": ["2011-01-25", "2017-12-26", "2017-12-27", "2023-09-07"],
    "COTE": ["2016-06-13"],
    "TTS": ["2024-08-16", "2024-08-19"],
}


def _patch_jumps(prices: pd.DataFrame, jumps: dict[str, list[str]] = JUMP_DATES) -> pd.DataFrame:
    """Rebuild each flagged column from its own returns, with the listed
    dates' returns zeroed -- see JUMP_DATES for why each one is an artifact,
    not a real move. Untouched columns/days pass through unchanged."""
    out = prices.copy()
    for ticker, dates in jumps.items():
        if ticker not in out.columns:
            continue
        s = out[ticker]
        first = s.first_valid_index()
        if first is None:
            continue
        ret = s.loc[first:].pct_change()
        bad = pd.DatetimeIndex([pd.Timestamp(d) for d in dates]).intersection(ret.index)
        ret.loc[bad] = 0.0
        out.loc[first:, ticker] = 100 * (1 + ret.fillna(0.0)).cumprod()
    return out


def fetch(tickers: list[str] = RAW_TICKERS, start: str = DATA_START) -> pd.DataFrame:
    """Adjusted daily closes, as-quoted in RON. No FX conversion needed --
    this account itself holds and trades in RON."""
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False, group_by="column", threads=False)
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].set_axis(tickers, axis=1)
    closes.index = pd.DatetimeIndex(closes.index).tz_localize(None).normalize()
    closes = closes[tickers]
    closes.columns = [t.removesuffix(".RO") for t in tickers]
    return closes


def load(refresh: bool = False) -> pd.DataFrame:
    """Raw BVB prices (jump-patched, see JUMP_DATES) plus a literal 0%-return
    CASH column (see package docstring)."""
    if not refresh and CACHE.is_file():
        prices = pd.read_parquet(CACHE)
    else:
        prices = _patch_jumps(fetch())
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(CACHE)
    out = prices.copy()
    out[CASH] = 100.0  # constant price -> 0% return every day
    return out
