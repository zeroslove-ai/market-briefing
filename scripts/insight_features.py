"""Deterministic features and thresholded anomalies for the canonical market board."""

from __future__ import annotations


THRESHOLDS = {
    "soxx_sp500_spread_pp": 2.0,
    "nasdaq_russell_spread_pp": 1.5,
    "nasdaq_sp500_spread_pp": 1.5,
    "us10y_change_bp": 5.0,
    "vix_change_pct": 8.0,
    "dxy_change_pct": 0.5,
    "wti_change_pct": 3.5,
    "gold_change_pct": 2.0,
    "silver_change_pct": 3.0,
    "btc_change_pct_24h": 5.0,
    "eth_change_pct_24h": 6.0,
}


def _q(board: dict, category: str, key: str) -> dict:
    value = board.get("indicators", {}).get(category, {}).get(key, {})
    return value if isinstance(value, dict) else {}


def _num(q: dict, key: str) -> float | None:
    value = q.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def calculate_features(board: dict) -> dict:
    """Return derived values only; source quotes remain unchanged."""
    equities = {key: _num(_q(board, "equities", key), "change_pct")
                for key in ("sp500", "nasdaq_composite", "russell_2000", "soxx")}
    rates = _num(_q(board, "rates", "us10y"), "change")
    assets = {
        "us10y_change_bp": rates * 100 if rates is not None else None,
        "vix_level": _num(_q(board, "volatility", "vix"), "price"),
        "vix_change_pct": _num(_q(board, "volatility", "vix"), "change_pct"),
        "dxy_change_pct": _num(_q(board, "fx", "dxy"), "change_pct"),
        "wti_change_pct": _num(_q(board, "commodities", "wti"), "change_pct"),
        "gold_change_pct": _num(_q(board, "commodities", "gold_futures"), "change_pct"),
        "silver_change_pct": _num(_q(board, "commodities", "silver_futures"), "change_pct"),
        "btc_change_pct_24h": _num(_q(board, "crypto", "btc"), "change_pct"),
        "eth_change_pct_24h": _num(_q(board, "crypto", "eth"), "change_pct"),
    }
    spreads = {
        "soxx_sp500_spread_pp": equities["soxx"] - equities["sp500"] if None not in (equities["soxx"], equities["sp500"]) else None,
        "nasdaq_russell_spread_pp": equities["nasdaq_composite"] - equities["russell_2000"] if None not in (equities["nasdaq_composite"], equities["russell_2000"]) else None,
        "nasdaq_sp500_spread_pp": equities["nasdaq_composite"] - equities["sp500"] if None not in (equities["nasdaq_composite"], equities["sp500"]) else None,
    }
    cash_values = [v for v in equities.values() if v is not None]
    cash_mean = sum(cash_values) / len(cash_values) if cash_values else 0
    cash_direction = 1 if cash_mean > 0 else -1 if cash_mean < 0 else 0
    futures = {key: _num(_q(board, "futures", key), "change_pct") for key in ("es", "nq", "rty")}
    valid_futures = [v for v in futures.values() if v is not None]
    future_mean = sum(valid_futures) / len(valid_futures) if valid_futures else 0
    futures_direction = 1 if future_mean > 0 else -1 if future_mean < 0 else 0
    features = {**equities, **spreads, **assets, "futures_change_pct": futures,
                "cash_session_direction": cash_direction, "futures_direction": futures_direction,
                "futures_vs_cash_direction": "confirming" if futures_direction == cash_direction and cash_direction else "diverging" if futures_direction and cash_direction and futures_direction != cash_direction else "neutral_or_unavailable"}
    confirmations = []
    for name, value in [
        ("equities", equities["sp500"]),
        ("growth", equities["nasdaq_composite"]),
        ("rates", -assets["us10y_change_bp"] if assets["us10y_change_bp"] is not None else None),
        ("volatility", -assets["vix_change_pct"] if assets["vix_change_pct"] is not None else None),
        ("dollar", -assets["dxy_change_pct"] if assets["dxy_change_pct"] is not None else None),
        ("crypto", assets["btc_change_pct_24h"]),
    ]:
        if value is not None and value > 0:
            confirmations.append(name)
    features["cross_asset_confirmation_count"] = len(confirmations)
    features["cross_asset_confirmations"] = confirmations
    return features


def detect_anomalies(features: dict) -> list[dict]:
    specs = [
        ("soxx_sp500_spread_pp", "SOXX vs S&P relative spread", "relative", "SOXX leadership / lag"),
        ("nasdaq_russell_spread_pp", "Nasdaq vs Russell spread", "relative", "growth vs small caps"),
        ("nasdaq_sp500_spread_pp", "Nasdaq vs S&P spread", "relative", "growth vs broad market"),
        ("us10y_change_bp", "US 10Y yield change", "absolute", "rates repricing"),
        ("vix_change_pct", "VIX change", "absolute", "volatility repricing"),
        ("dxy_change_pct", "DXY change", "absolute", "dollar repricing"),
        ("wti_change_pct", "WTI change", "absolute", "oil repricing"),
        ("gold_change_pct", "Gold change", "absolute", "gold repricing"),
        ("silver_change_pct", "Silver change", "absolute", "silver repricing"),
        ("btc_change_pct_24h", "BTC 24h change", "absolute", "crypto repricing"),
        ("eth_change_pct_24h", "ETH 24h change", "absolute", "crypto repricing"),
    ]
    anomalies = []
    for metric, label, kind, reason in specs:
        value = features.get(metric)
        threshold = THRESHOLDS[metric]
        if not isinstance(value, (int, float)) or abs(value) < threshold:
            continue
        severity = "HIGH" if abs(value) >= threshold * (1.5 if kind == "relative" else 1.5) else "MEDIUM"
        anomalies.append({
            "anomaly_id": metric, "severity": severity,
            "direction": "up" if value > 0 else "down", "metric": label,
            "value": round(value, 4), "threshold": threshold,
            "reason": f"절대값이 기준 {threshold:g}을 넘어선 {reason} 움직임",
        })
    return anomalies
