"""Alpaca client for the stocks lab's OWN, separate paper account.

Reuses tae2.broker.AlpacaPaper unchanged -- it already takes key_id/secret/
base_url as plain constructor arguments and refuses any non-paper URL
itself, so there is nothing ETF-specific to duplicate. Only from_env()
differs, and deliberately so: it reads STOCKS_ALPACA_API_KEY_ID /
STOCKS_ALPACA_API_SECRET_KEY, never tae2's ALPACA_API_KEY_ID /
ALPACA_API_SECRET_KEY, so the two labs can never end up pointed at the same
account by accident (two separate Alpaca paper accounts, nicknamed
"MoVo10" for this one).
"""

from __future__ import annotations

import os

from tae2.broker import PAPER_URL, AlpacaPaper, Account, BrokerError, Position, load_dotenv  # noqa: F401 (re-exported)


def from_env() -> AlpacaPaper:
    load_dotenv()
    return AlpacaPaper(
        os.environ.get("STOCKS_ALPACA_API_KEY_ID", ""),
        os.environ.get("STOCKS_ALPACA_API_SECRET_KEY", ""),
        os.environ.get("STOCKS_ALPACA_BASE_URL", PAPER_URL),
    )
