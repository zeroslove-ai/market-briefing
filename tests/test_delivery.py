from datetime import datetime

import delivery_render
import morning_delivery
import state_store
from market_clock import KST


def sample_payload():
    def q(price, change_pct, change=None):
        return {"price": price, "change_pct": change_pct, "change": change, "stale": False}

    return {
        "session_date": "2026-09-22",
        "delivery": {"mode": "close_autopsy", "delivery_date": "2026-09-23"},
        "indicators": {
            "equities": {
                "sp500": q(7764.64, 0.0),
                "nasdaq_composite": q(27244.28, 0.45),
                "russell_2000": q(2889.92, 0.51),
                "soxx": q(420.0, -0.8),
            },
            "futures": {"es": q(7800, 0.2), "nq": q(28000, 0.3), "rty": q(2900, -0.1)},
            "rates": {"us10y": q(4.968, 0.1, 0.005)},
            "volatility": {"vix": q(14.21, -4.44)},
            "fx": {"dxy": q(100.54, 0.11)},
            "commodities": {
                "wti": q(90.01, -6.02),
                "gold_futures": q(3800, 0.2),
                "silver_futures": q(47.5, 0.4),
            },
            "crypto": {"btc": q(65000, 1.2), "eth": q(3500, -0.5)},
        },
        "news": [{"time": "09-23 05:40", "title": "AI stocks lead the market"}],
        "econ_calendar": [{
            "time": "09-23 22:45", "event": "US Flash Manufacturing PMI", "importance": 3,
            "forecast": "53.5", "previous": "53.9", "actual": "",
        }],
        "earnings": [{
            "symbol": "PAYX", "name": "Paychex", "time": "pre-market",
            "eps_forecast": "$1.32",
        }],
        "options": {"NVDA": {"iv30": 0.42, "total_oi": 1000, "oi_change": 20}},
        "data_quality": [],
    }


def test_delivery_mode_week_kickoff_close_autopsy_and_sunday_skip():
    assert morning_delivery.delivery_mode(datetime(2026, 9, 28, 6, 30, tzinfo=KST)) == "week_kickoff"
    assert morning_delivery.delivery_mode(datetime(2026, 9, 26, 6, 30, tzinfo=KST)) == "close_autopsy"
    assert morning_delivery.delivery_mode(datetime(2026, 9, 27, 6, 30, tzinfo=KST)) == "skip"


def test_morning_delivery_window_is_bounded():
    assert morning_delivery.within_delivery_window(datetime(2026, 9, 23, 6, 30, tzinfo=KST))
    assert morning_delivery.within_delivery_window(datetime(2026, 9, 23, 7, 45, tzinfo=KST))
    assert not morning_delivery.within_delivery_window(datetime(2026, 9, 23, 8, 1, tzinfo=KST))


def test_telegram_contains_cross_asset_board_kst_calendar_and_earnings():
    messages = delivery_render.render_telegram_compact(sample_payload())
    text = "\n".join(messages)
    assert "S&P" in text and "Nasdaq" in text and "SOXX" in text
    assert "10Y 4.968%" in text and "VIX" in text and "DXY" in text
    assert "WTI" in text and "Gold" in text and "Silver" in text
    assert "BTC" in text and "ETH" in text and "24h" in text
    assert "09-23 22:45 KST" in text
    assert "PAYX" in text and "장전" in text
    assert all(len(message) <= 3500 for message in messages)


def test_telegram_calendar_fallback_still_labels_kst():
    payload = sample_payload()
    payload["econ_calendar"] = [{"error": "HTTP 403"}]
    text = "\n".join(delivery_render.render_telegram_compact(payload))
    assert "오늘 일정 (KST)" in text
    assert "경제 캘린더 소스 확인 필요" in text


def test_email_full_and_telegram_use_same_payload_facts():
    payload = sample_payload()
    subject, plain, html = delivery_render.render_email_full(payload)
    telegram = "\n".join(delivery_render.render_telegram_compact(payload))
    for token in ("Nasdaq", "WTI", "BTC", "PAYX", "22:45"):
        assert token in plain
        assert token in telegram
    assert "06:30 KST" in subject
    assert "<html>" in html
    assert "<h2>옵션 / OI</h2>" in html
    assert "NVDA | IV30 +42.0% | OI 1000" in html


def test_morning_option_context_reads_canonical_close_state(monkeypatch, tmp_path):
    monkeypatch.setattr(state_store, "STATE_ROOT", tmp_path)
    state_store.atomic_write_json(state_store.state_path("option", "oi_close_snapshot.json"), {
        "session_date": "2026-09-22",
        "snapshots": {"NVDA": {"call_oi": 120, "put_oi": 80, "total_oi": 200}},
        "previous_snapshots": {"NVDA": {"call_oi": 100, "put_oi": 70, "total_oi": 170}},
    })
    state_store.atomic_write_json(state_store.state_path("option", "flow_signals.json"), {
        "signals": [{"ticker": "NVDA", "iv30": 0.42}],
    })
    options = morning_delivery._load_option_context({"options": {"OLD": {"total_oi": 1}}})
    assert options["NVDA"] == {
        "call_oi": 120, "put_oi": 80, "total_oi": 200, "oi_change": 30, "iv30": 0.42,
    }
    assert "OLD" not in options


def test_delivery_ledger_is_channel_specific_and_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr(state_store, "STATE_ROOT", tmp_path)
    payload = sample_payload()
    assert not morning_delivery.already_sent(payload, "telegram")
    morning_delivery.mark_delivery(payload, "telegram", "sent")
    assert morning_delivery.already_sent(payload, "telegram")
    assert not morning_delivery.already_sent(payload, "email")


def test_write_artifacts_produces_payload_email_and_telegram(monkeypatch, tmp_path):
    monkeypatch.setattr(state_store, "STATE_ROOT", tmp_path)
    payload = sample_payload()
    rendered = morning_delivery.write_artifacts(payload)
    assert all(__import__("pathlib").Path(path).exists() for path in rendered["paths"].values())
    assert "PAYX" in __import__("pathlib").Path(rendered["paths"]["telegram"]).read_text(encoding="utf-8")
    gmail_handoff = __import__("json").loads(__import__("pathlib").Path(rendered["paths"]["gmail_mcp"]).read_text(encoding="utf-8"))
    assert gmail_handoff["provider"] == "gmail_mcp"
    assert gmail_handoff["recipient_strategy"] == "authenticated_profile_self"
    assert "PAYX" in gmail_handoff["body"]
    assert "GMAIL_APP_PASSWORD" not in str(gmail_handoff)
