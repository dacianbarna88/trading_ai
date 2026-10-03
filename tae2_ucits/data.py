"""Price data for the UCITS-accessible twin of core_gtaa_50.

Every ticker below was individually verified via yfinance (real price
history AND fund identity via .info -- a wrong guess, "IQQH.DE", was
caught exactly this way before being trusted) on 2026-10-03. None of this
is a code-path reused from tae2/data.py's fetch() -- that function hard-
codes tae2.config.CALENDAR_TICKER ("SPY"), which doesn't exist in this
ticker list, so it would crash; this is a small, standalone fetch instead.

Six tae2 legs, six UCITS stand-ins:

| tae2 ticker | UCITS ticker(s)                  | Real history starts |
|-------------|-----------------------------------|----------------------|
| SPY         | CSPX.L (iShares Core S&P 500)      | 2010-09-15           |
| IEF         | IDTM.L (iShares $ Treasury 7-10yr) | 2009-01-02           |
| VNQ         | IUSP.L (iShares US Property Yield) | 2009-01-02           |
| SHY         | IBTS.L (iShares $ Treasury 1-3yr)  | 2008-01-02           |
| EFA         | EXSA.DE + IQQJ.DE + CPXJ.L blend   | 2010-09-28 (blended) |
| DBC         | CMOD.L, spliced onto DBC pre-2017  | 2006 (spliced)       |

APPROXIMATIONS, read before trusting a result:
- EFA is approximated as a fixed-weight blend of iShares STOXX Europe 600
  (EXSA.DE, 65%), iShares MSCI Japan (IQQJ.DE, 22%) and iShares Core MSCI
  Pacific ex-Japan (CPXJ.L, 13%) -- roughly MSCI EAFE's real regional
  split, but static, not the index's own periodic reweighting. CPXJ's
  2010-09-28 start is the binding constraint for this leg.
- DBC's commodity leg has no UCITS equivalent with long history (the best
  found, CMOD.L, only starts 2017-01-09). Pre-2017 returns are approximated
  using the original US-listed DBC's own real returns for that period
  (DBC itself launched Feb 2006, tracking a different index -- Deutsche
  Bank's DBIQ -- than CMOD's Bloomberg Commodity Index, and without CMOD's
  own currency/UCITS-wrapper tracking error). From 2017-01-09 onward, this
  uses CMOD's real returns.
- All other tickers are real, direct UCITS funds with no splicing.

The combined/spliced result is intentionally given the SAME column names
tae2.strategies' functions expect (SPY, EFA, IEF, DBC, VNQ, SHY) so
tae2.engine.DEPLOYABLE["core_gtaa_50"] and tae2.backtest.run() can be
called completely unchanged -- only the input data differs.

TWO VARIANTS, never blurred together:

- STRICT (build_strict / load("strict")): only real, clean UCITS history.
  Starts 2011-06-01 in practice (see tae2_ucits/research.py's EVAL_START note
  -- IBTS.L and IUSP.L are real funds back to 2008-2009 but Yahoo's feed for
  both is corrupted through ~2011-05). The conservative test: every number in
  it is a real UCITS fund's real price.

- EXTENDED (build_extended / load("extended")): recovers 2008-2011 by
  splicing, for SPY/IEF/VNQ/SHY/EFA only, the ORIGINAL US ticker's own real
  returns before the UCITS fund's clean-data start, switching to the real
  UCITS fund from then on -- exactly the same technique already used for
  DBC (US DBC -> CMOD.L), just with a different splice date chosen for a
  different reason (a data-quality gap, not a short fund history). DBC's
  own existing splice already reaches back to 2006 and is left unchanged.

      2008 ──────────── 2011-06-01 │ 2011-06-01 ──────────────── today
           PROXY (original US ETF)  │   UCITS REAL (own fund)
                                    ↑ splice date (RECOVERY_SPLICE_DATE)

  This is a documented reconstruction, not "real UCITS history" -- useful
  specifically to test whether the STRICT variant's first-half gate failure
  is caused by excluding the 2008 crisis, not by anything UCITS-specific.
  Built 2026-10-03 after autopsy.py showed the same failure on pure US data
  restricted to the same short window.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_STRICT = Path("data_cache/tae2_ucits_prices.parquet")
CACHE_EXTENDED = Path("data_cache/tae2_ucits_prices_extended.parquet")
DATA_START = "2005-01-01"

RECOVERY_SPLICE_DATE = "2011-06-01"  # STRICT's own clean-data start (see above)
RECOVERY_LEGS = ("SPY", "IEF", "VNQ", "SHY", "EFA")  # DBC already has its own, earlier splice

SPY_TICKER = "CSPX.L"
IEF_TICKER = "IDTM.L"
VNQ_TICKER = "IUSP.L"
SHY_TICKER = "IBTS.L"
EUROPE_TICKER = "EXSA.DE"
JAPAN_TICKER = "IQQJ.DE"
PACIFIC_TICKER = "CPXJ.L"
DBC_UCITS_TICKER = "CMOD.L"
DBC_SPLICE_TICKER = "DBC"  # original US fund; proxy for the pre-CMOD period only
DBC_SPLICE_DATE = "2017-01-09"  # CMOD's own first real trading day

EAFE_WEIGHTS = {EUROPE_TICKER: 0.65, JAPAN_TICKER: 0.22, PACIFIC_TICKER: 0.13}

ALL_TICKERS = [
    SPY_TICKER, IEF_TICKER, VNQ_TICKER, SHY_TICKER,
    EUROPE_TICKER, JAPAN_TICKER, PACIFIC_TICKER,
    DBC_UCITS_TICKER, DBC_SPLICE_TICKER,
]


def fetch(tickers: list[str], start: str = DATA_START) -> pd.DataFrame:
    """Adjusted daily closes, as-quoted on each ticker's own exchange/currency.

    No cross-currency conversion: a EUR-quoted Xetra listing's returns are
    exactly what an investor buying that specific listing would see,
    including whatever FX is embedded in the quote -- that's the honest
    number for this purpose, not a distortion to correct.
    """
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False, group_by="column", threads=False)
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].set_axis(tickers, axis=1)
    closes.index = pd.DatetimeIndex(closes.index).tz_localize(None).normalize()
    return closes[tickers]


def _blended_index(prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """A synthetic price index: weighted-average daily return of the
    components, compounded from 100, starting the first day all components
    have data (not the first day any one of them does)."""
    rets = prices[list(weights)].pct_change()
    ready = rets.dropna(how="any")
    weighted_return = sum(ready[t] * w for t, w in weights.items())
    return 100 * (1 + weighted_return).cumprod()


def _splice_returns(early: pd.Series, late: pd.Series, splice_date: str) -> pd.Series:
    """One continuous index: `early`'s own returns before `splice_date`,
    `late`'s own returns from `splice_date` onward, chained so there's no
    artificial jump at the seam. `early` and `late` may be on different
    calendars (each is pct_change'd on its own index first) -- that's the
    point: it lets a US-calendar series splice onto a UCITS-calendar one."""
    early_ret = early.pct_change().dropna()
    late_ret = late.pct_change().dropna()
    splice = pd.Timestamp(splice_date)
    combined_ret = pd.concat([early_ret.loc[early_ret.index < splice], late_ret.loc[late_ret.index >= splice]])
    return 100 * (1 + combined_ret.sort_index()).cumprod()


def _spliced_index(prices: pd.DataFrame, early_ticker: str, late_ticker: str, splice_date: str) -> pd.Series:
    """Same as `_splice_returns`, for two columns that already share a calendar."""
    return _splice_returns(prices[early_ticker], prices[late_ticker], splice_date)


def _strict_columns(raw: pd.DataFrame) -> pd.DataFrame:
    """build_strict()'s six columns, WITHOUT the final row-level dropna --
    SPY/IEF/VNQ/SHY keep their natural leading NaNs (each starts on its own
    ticker's real first trading day). build_extended() needs this
    intermediate form so it can splice each leg on ITS OWN earliest real
    date, not on the date all six already happen to overlap."""
    out = pd.DataFrame(index=raw.index)
    out["SPY"] = raw[SPY_TICKER]
    out["IEF"] = raw[IEF_TICKER]
    out["VNQ"] = raw[VNQ_TICKER]
    out["SHY"] = raw[SHY_TICKER]
    out["EFA"] = _blended_index(raw, EAFE_WEIGHTS)
    out["DBC"] = _spliced_index(raw, DBC_SPLICE_TICKER, DBC_UCITS_TICKER, DBC_SPLICE_DATE)
    return out


def build_strict(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename/combine the raw UCITS tickers into tae2's own column names.
    Real UCITS history only -- see the STRICT variant note above."""
    return _strict_columns(raw).dropna(how="any")


def build_extended(raw: pd.DataFrame, us_prices: pd.DataFrame) -> pd.DataFrame:
    """build_strict() plus the pre-2011-06-01 recovery splice -- see the
    EXTENDED variant note above. `us_prices` must have SPY/IEF/VNQ/SHY/EFA
    columns with real history back to at least 2008 (tae2.data.load()'s own
    cache: the ORIGINAL US tickers tae2 itself trades).

    Splices from _strict_columns() (pre-dropna), not build_strict()'s own
    output -- splicing onto the already-dropna'd frame would silently clip
    every recovered pre-2011 date right back off (each leg's UCITS half
    must keep its own natural start date until the final dropna, below)."""
    strict = _strict_columns(raw)
    spliced = {leg: _splice_returns(us_prices[leg], strict[leg], RECOVERY_SPLICE_DATE) for leg in RECOVERY_LEGS}
    out = pd.DataFrame(spliced)
    out["DBC"] = strict["DBC"]
    return out.dropna(how="any")


def load(variant: str = "strict", refresh: bool = False) -> pd.DataFrame:
    if variant not in ("strict", "extended"):
        raise ValueError(f"unknown variant {variant!r}; choose 'strict' or 'extended'")
    cache = CACHE_STRICT if variant == "strict" else CACHE_EXTENDED
    if not refresh and cache.is_file():
        return pd.read_parquet(cache)
    raw = fetch(ALL_TICKERS)
    if variant == "strict":
        prices = build_strict(raw)
    else:
        from tae2 import data as us_data

        us_prices, _ = us_data.load(refresh=False)
        prices = build_extended(raw, us_prices)
    cache.parent.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(cache)
    return prices
