"""Canonical cross-asset Market Board collector for R1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from market_data import RunCache, yahoo_chart_quote

ASSETS = {
    "equities": {
        "sp500": "^GSPC", "nasdaq_composite": "^IXIC", "nasdaq_100": "^NDX",
        "dow": "^DJI", "russell_2000": "^RUT", "soxx": "SOXX",
    },
    "futures": {"es": "ES=F", "nq": "NQ=F", "ym": "YM=F", "rty": "RTY=F"},
    "rates": {"us10y": "^TNX", "us30y": "^TYX"},
    "volatility": {"vix": "^VIX"},
    "fx": {"dxy": "DX-Y.NYB", "usd_krw": "KRW=X"},
    "commodities": {"wti": "CL=F", "gold_futures": "GC=F", "silver_futures": "SI=F"},
    "crypto": {"btc": "BTC-USD", "eth": "ETH-USD"},
}


def _crypto_quote(symbol: str, cache: RunCache) -> dict:
    # Yahoo's one-hour candles give an explicit 24-hour comparison window.
    from market_data import _fetch_json, fetch_url
    import urllib.parse
    from datetime import datetime, timedelta, timezone

    key = f"yahoo-crypto-24h:{symbol}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    url = "https://query1.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(symbol) + "?range=2d&interval=1h"
    document = _fetch_json(url, 20, fetch_url)
    result = document["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
    valid = [(ts, close) for ts, close in zip(timestamps, closes) if close is not None]
    if len(valid) < 2:
        raise ValueError(f"Yahoo returned insufficient crypto candles for {symbol}")
    last_ts, price = valid[-1]
    target = last_ts - 24 * 60 * 60
    prior_ts, prior = min(valid[:-1], key=lambda item: abs(item[0] - target))
    change_pct = (price - prior) / prior * 100 if prior else None
    output = {
        "symbol": symbol,
        "price": price,
        "prev": prior,
        "change": price - prior,
        "change_pct": round(change_pct, 6) if change_pct is not None else None,
        "source": "yahoo_crypto",
        "timestamp": datetime.fromtimestamp(last_ts, tz=timezone.utc).isoformat(),
        "reference_window": "24h",
        "stale": False,
    }
    return cache.put(key, output)


def collect_market_board(cache: Optional[RunCache] = None) -> dict:
    cache = cache or RunCache()
    indicators = {category: {} for category in ASSETS}
    generated_at = datetime.now(timezone.utc).isoformat()
    errors = []
    for category, symbols in ASSETS.items():
        for key, symbol in symbols.items():
            try:
                quote = _crypto_quote(symbol, cache) if category == "crypto" else yahoo_chart_quote(symbol, cache)
                indicators[category][key] = quote
            except Exception as error:
                errors.append(f"{category}.{key}: {str(error)[:120]}")
                indicators[category][key] = {
                    "symbol": symbol, "source": "unavailable", "timestamp": generated_at,
                    "reference_window": "24h" if category == "crypto" else "regular_session_daily",
                    "stale": True, "error": str(error)[:120],
                }
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "indicators": indicators,
        "data_quality": errors,
    }

