"""Minimal Alpaca client, paper trading only.

The paper URL is hard-wired and any other base URL is refused, so this code
cannot place an order with real money. Keys come from the environment
(ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY, usually via a local .env file)
and are never logged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PAPER_URL = "https://paper-api.alpaca.markets"


class BrokerError(RuntimeError):
    pass


def load_dotenv(path: Path = Path(".env")) -> None:
    """Put KEY=VALUE lines from `path` into os.environ (existing values win)."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    market_value: float


@dataclass(frozen=True)
class Account:
    equity: float
    cash: float
    buying_power: float
    status: str
    trading_blocked: bool


class AlpacaPaper:
    def __init__(self, key_id: str, secret: str, base_url: str = PAPER_URL, session: Any = None) -> None:
        if base_url.rstrip("/") != PAPER_URL:
            raise BrokerError(f"refusing non-paper Alpaca URL {base_url!r}; TAE 2.0 trades paper only")
        if not key_id or not secret:
            raise BrokerError("missing ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY")
        if session is None:
            import requests

            session = requests.Session()
        self._s = session
        self._s.headers.update({"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret})
        self.base_url = PAPER_URL

    @classmethod
    def from_env(cls) -> "AlpacaPaper":
        load_dotenv()
        return cls(
            os.environ.get("ALPACA_API_KEY_ID", ""),
            os.environ.get("ALPACA_API_SECRET_KEY", ""),
            os.environ.get("ALPACA_BASE_URL", PAPER_URL),
        )

    def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = self._s.request(method, f"{self.base_url}{path}", timeout=30, **kwargs)
        if resp.status_code >= 400:
            raise BrokerError(f"{method} {path} -> {resp.status_code}: {resp.text[:300]}")
        return resp.json() if resp.text else None

    def clock(self) -> dict:
        return self._call("GET", "/v2/clock")

    def account(self) -> Account:
        a = self._call("GET", "/v2/account")
        return Account(
            equity=float(a["equity"]),
            cash=float(a["cash"]),
            buying_power=float(a["buying_power"]),
            status=str(a.get("status")),
            trading_blocked=bool(a.get("trading_blocked") or a.get("account_blocked")),
        )

    def positions(self) -> list[Position]:
        return [
            Position(p["symbol"], float(p["qty"]), float(p["market_value"]))
            for p in self._call("GET", "/v2/positions")
        ]

    def open_orders(self) -> list[dict]:
        return self._call("GET", "/v2/orders", params={"status": "open"})

    def order(self, order_id: str) -> dict:
        return self._call("GET", f"/v2/orders/{order_id}")

    def submit(self, symbol: str, side: str, *, notional: float | None = None, qty: float | None = None) -> dict:
        """Market day order, sized by dollars (`notional`) or shares (`qty`)."""
        if (notional is None) == (qty is None):
            raise BrokerError("pass exactly one of notional / qty")
        body: dict[str, Any] = {"symbol": symbol, "side": side, "type": "market", "time_in_force": "day"}
        if notional is not None:
            body["notional"] = f"{notional:.2f}"
        else:
            body["qty"] = f"{qty:.6f}"
        return self._call("POST", "/v2/orders", json=body)
