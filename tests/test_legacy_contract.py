import json

import us_market_report


def test_option_price_fields_are_yahoo_not_cboe(monkeypatch):
    monkeypatch.setattr(us_market_report, "cboe_chain_summary", lambda *args, **kwargs: {
        "call_oi": 10, "put_oi": 20, "total_oi": 30, "iv30": 0.4, "sd_pct": 11,
        "oi_top": [{"strike": 100, "type": "C", "oi": 10}], "atm": {"strike": 100},
        "current_price": 999, "price_change_percent": 88,
    })
    output = us_market_report._cboe_option_data("NVDA", {
        "price": 101, "change_pct": 1.5, "source": "yahoo_regular_ohlc",
    }, None)
    assert output["price"] == 101
    assert output["change_pct"] == 1.5
    assert output["price_source"] == "yahoo_regular_ohlc"
    assert output["price"] != 999
    assert output["oi_top"] and output["atm"]["strike"] == 100


def test_earnings_query_uses_target_us_session_date(monkeypatch):
    urls = []

    def fake_fetch(url, timeout=15):
        urls.append(url)
        return json.dumps({"data": {"rows": []}}).encode()

    monkeypatch.setattr(us_market_report, "fetch", fake_fetch)
    us_market_report.collect_earnings(__import__("datetime").date(2026, 9, 22))
    assert "date=2026-09-22" in urls[0]
