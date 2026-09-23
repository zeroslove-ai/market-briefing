"""Shared public-market collectors with a per-run cache.

Yahoo daily regular-session OHLC is the price authority. CBOE is deliberately
limited to IV/open-interest/Greeks fields.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from market_clock import ET, last_actual_regular_session

UA = {"User-Agent": "Mozilla/5.0 (Hermes R1 data core)"}
Fetcher = Callable[[str, int], bytes]


def fetch_url(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class RunCache:
    def __init__(self) -> None:
        self._values: dict[str, object] = {}

    def get(self, key: str):
        return self._values.get(key)

    def put(self, key: str, value):
        self._values[key] = value
        return value


def _fetch_json(url: str, timeout: int, fetcher: Fetcher) -> dict:
    return json.loads(fetcher(url, timeout))


def yahoo_chart_quote(symbol: str, cache: Optional[RunCache] = None, fetcher: Fetcher = fetch_url) -> dict:
    cache = cache or RunCache()
    key = f"yahoo-daily:{symbol}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=5d&interval=1d"
    document = _fetch_json(url, 20, fetcher)
    result = document["chart"]["result"][0]
    meta = result.get("meta", {})
    timestamps = result.get("timestamp", [])
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    closes = quote.get("close", [])
    valid = [(ts, close) for ts, close in zip(timestamps, closes) if close is not None]
    if not valid:
        raise ValueError(f"Yahoo returned no regular-session close for {symbol}")
    last_ts, price = valid[-1]
    prev = valid[-2][1] if len(valid) >= 2 else None
    session_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc).astimezone(ET)
    change = round(price - prev, 6) if prev is not None else None
    change_pct = round(change / prev * 100, 6) if change is not None and prev else None
    output = {
        "symbol": symbol,
        "name": meta.get("shortName") or meta.get("longName") or symbol,
        "price": price,
        "prev": prev,
        "change": change,
        "change_pct": change_pct,
        "data_date": session_dt.strftime("%Y-%m-%d"),
        "et_date": session_dt.strftime("%Y-%m-%d(%a)"),
        "source": "yahoo_regular_ohlc",
        "timestamp": datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat(),
        "reference_window": "regular_session_daily",
        "stale": session_dt.date() < last_actual_regular_session(),
    }
    return cache.put(key, output)


def yahoo_daily_last(symbol: str, cache: Optional[RunCache] = None, fetcher: Fetcher = fetch_url) -> dict:
    cache = cache or RunCache()
    key = f"yahoo-ohlc:{symbol}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=5d&interval=1d"
    document = _fetch_json(url, 20, fetcher)
    result = document["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result.get("indicators", {}).get("quote", [{}])[0]
    valid = [(ts, h, low, close) for ts, h, low, close in zip(
        timestamps, quote.get("high", []), quote.get("low", []), quote.get("close", []))
        if close is not None and h is not None and low is not None
    ]
    if not valid:
        raise ValueError(f"Yahoo returned no OHLC for {symbol}")
    ts, high, low, close = valid[-1]
    output = {
        "date": datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(ET).strftime("%Y-%m-%d(%a)"),
        "high": high,
        "low": low,
        "close": close,
        "source": "yahoo_regular_ohlc",
    }
    return cache.put(key, output)


def cboe_chain_summary(symbol: str, cache: Optional[RunCache] = None, fetcher: Fetcher = fetch_url,
                       sleep_seconds: float = 1.5, reference_price: Optional[float] = None) -> dict:
    cache = cache or RunCache()
    key = f"cboe-chain:{symbol}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"
    last_error = None
    document = None
    for attempt in range(4):
        try:
            document = _fetch_json(url, 25, fetcher)
            break
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code != 429:
                raise
            time.sleep(10 * (attempt + 1))
        except Exception as error:  # network resets are safe to retry once per attempt
            last_error = error
            time.sleep(2)
    if document is None:
        raise last_error or RuntimeError(f"CBOE request failed for {symbol}")
    if sleep_seconds:
        time.sleep(sleep_seconds)
    data = document["data"]
    call_oi = put_oi = 0
    for option in data.get("options") or []:
        name = option.get("option") or ""
        if len(name) < 9:
            continue
        open_interest = option.get("open_interest") or 0
        if name[-9] == "C":
            call_oi += open_interest
        elif name[-9] == "P":
            put_oi += open_interest
    oi_top = []
    for option in sorted(data.get("options") or [], key=lambda item: item.get("open_interest") or 0, reverse=True)[:3]:
        name = option.get("option") or ""
        try:
            oi_top.append({
                "strike": int(name[-8:]) / 1000,
                "type": name[-9],
                "oi": option.get("open_interest"),
                "iv": round(option.get("iv") or 0, 4),
            })
        except (ValueError, TypeError, IndexError):
            continue
    atm = None
    if reference_price is not None and data.get("options"):
        valid_options = []
        for option in data.get("options") or []:
            name = option.get("option") or ""
            try:
                valid_options.append((abs(int(name[-8:]) / 1000 - reference_price), option, int(name[-8:]) / 1000))
            except (ValueError, TypeError, IndexError):
                continue
        if valid_options:
            _, option, strike = min(valid_options, key=lambda item: item[0])
            atm = {"strike": strike, "type": (option.get("option") or "")[-9],
                   "iv": round(option.get("iv") or 0, 4), "oi": option.get("open_interest")}
    iv30_raw = data.get("iv30")
    iv30 = (iv30_raw / 100) if iv30_raw and iv30_raw > 1 else iv30_raw
    output = {
        "call_oi": call_oi,
        "put_oi": put_oi,
        "total_oi": call_oi + put_oi,
        "iv30": iv30,
        "sd_pct": round(iv30 * (30 / 365) ** 0.5 * 100, 2) if iv30 else None,
        "oi_top": oi_top,
        "atm": atm,
        "source": "cboe_options",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reference_window": "options_chain",
        "stale": False,
    }
    return cache.put(key, output)
