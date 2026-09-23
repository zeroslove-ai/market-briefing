import json
from datetime import date, datetime, timezone

import market_board
import phase_gate
import state_store
from market_clock import ET, KST, get_market_clock, target_us_session_date
from market_data import RunCache, yahoo_chart_quote
from report_snapshots import compute_changes


def test_dst_timezone_offsets_are_named_and_change_with_dst():
    winter = get_market_clock(now=datetime(2026, 1, 5, 12, tzinfo=timezone.utc))
    summer = get_market_clock(now=datetime(2026, 7, 6, 12, tzinfo=timezone.utc))
    assert winter.now_et.utcoffset().total_seconds() == -5 * 3600
    assert summer.now_et.utcoffset().total_seconds() == -4 * 3600
    assert winter.now_kst.tzinfo == KST
    assert summer.now_et.tzinfo == ET


def test_session_dates_use_us_calendar_not_kst_calendar():
    # 07:00 KST is the prior US evening and reports the prior completed US day.
    morning = datetime(2026, 9, 23, 7, 0, tzinfo=KST)
    close = datetime(2026, 9, 23, 5, 5, tzinfo=KST)
    evening = datetime(2026, 9, 23, 21, 0, tzinfo=KST)
    assert target_us_session_date("morning", morning) == date(2026, 9, 22)
    assert target_us_session_date("close", close) == date(2026, 9, 22)
    assert target_us_session_date("evening", evening) == date(2026, 9, 23)


def test_new_years_day_observed_on_prior_december_31_is_closed():
    from market_clock import is_regular_session_day, previous_regular_session
    assert not is_regular_session_day(date(2021, 12, 31))
    assert previous_regular_session(date(2022, 1, 1)) == date(2021, 12, 30)


def test_open_close_gate_tracks_dst_and_skips_observed_holiday():
    winter_open = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
    summer_open = datetime(2026, 3, 9, 13, 30, tzinfo=timezone.utc)
    winter_close = datetime(2026, 1, 5, 21, 5, tzinfo=timezone.utc)
    summer_close = datetime(2026, 3, 9, 20, 5, tzinfo=timezone.utc)
    holiday_open = datetime(2021, 12, 31, 14, 30, tzinfo=timezone.utc)
    assert phase_gate.is_phase_due("open", winter_open)
    assert phase_gate.is_phase_due("open", summer_open)
    assert phase_gate.is_phase_due("close", winter_close)
    assert phase_gate.is_phase_due("close", summer_close)
    assert not phase_gate.is_phase_due("open", holiday_open)
    assert not phase_gate.is_phase_due("open", summer_open.replace(hour=14))


def test_morning_delivery_friday_to_monday_session_matrix():
    cases = [
        (datetime(2026, 9, 25, 6, 30, tzinfo=KST), True, "2026-09-24"),  # Fri KST / Thu ET
        (datetime(2026, 9, 26, 6, 30, tzinfo=KST), True, "2026-09-25"),  # Sat KST / Fri ET
        (datetime(2026, 9, 27, 6, 30, tzinfo=KST), False, None),          # Sun KST / Sat ET
        (datetime(2026, 9, 28, 6, 30, tzinfo=KST), False, None),          # Mon KST / Sun ET
    ]
    for now, expected, session_date in cases:
        decision = phase_gate.delivery_decision("morning", now)
        assert decision["eligible"] is expected
        assert decision["session_date"] == session_date


def test_evening_delivery_friday_to_monday_session_matrix():
    cases = [
        (datetime(2026, 9, 25, 21, 0, tzinfo=KST), True, "2026-09-25"),
        (datetime(2026, 9, 26, 21, 0, tzinfo=KST), False, None),
        (datetime(2026, 9, 27, 21, 0, tzinfo=KST), False, None),
        (datetime(2026, 9, 28, 21, 0, tzinfo=KST), True, "2026-09-28"),
    ]
    for now, expected, session_date in cases:
        decision = phase_gate.delivery_decision("evening", now)
        assert decision["eligible"] is expected
        assert decision["session_date"] == session_date


def test_morning_reboot_catchup_is_bounded_and_marked_late():
    catchup = phase_gate.delivery_decision("morning", datetime(2026, 9, 22, 6, 40, tzinfo=KST))
    expired = phase_gate.delivery_decision("morning", datetime(2026, 9, 22, 8, 30, tzinfo=KST))
    assert catchup["eligible"] and catchup["delivery_status"] == "catchup"
    assert catchup["late"] is True and catchup["catchup"] is True
    assert not expired["eligible"]


def test_evening_catchup_respects_dst_open_and_two_hour_cap():
    # In EDT the open is 22:30 KST; in EST it is 23:30 KST.
    edt_before_open = phase_gate.delivery_decision("evening", datetime(2026, 3, 10, 22, 25, tzinfo=KST))
    edt_after_open = phase_gate.delivery_decision("evening", datetime(2026, 3, 10, 22, 31, tzinfo=KST))
    est_before_limit = phase_gate.delivery_decision("evening", datetime(2026, 1, 6, 22, 50, tzinfo=KST))
    est_after_limit = phase_gate.delivery_decision("evening", datetime(2026, 1, 6, 23, 1, tzinfo=KST))
    assert edt_before_open["eligible"] and edt_before_open["late"]
    assert not edt_after_open["eligible"]
    assert est_before_limit["eligible"] and est_before_limit["delivery_status"] == "catchup"
    assert not est_after_limit["eligible"]


def test_kst_delivery_eligibility_skips_us_holidays_and_carries_catchup_state(monkeypatch, tmp_path):
    import subprocess
    monkeypatch.setattr(state_store, "STATE_ROOT", tmp_path)
    runs = []
    monkeypatch.setattr(phase_gate.subprocess, "run", lambda *args, **kwargs: runs.append(args) or subprocess.CompletedProcess(args[0], 0))
    holiday_morning = phase_gate.delivery_decision("morning", datetime(2026, 9, 8, 6, 40, tzinfo=KST))
    holiday_evening = phase_gate.delivery_decision("evening", datetime(2026, 9, 7, 21, 0, tzinfo=KST))
    assert not holiday_morning["eligible"]
    assert not holiday_evening["eligible"]

    catchup_time = datetime(2026, 9, 22, 6, 40, tzinfo=KST)
    assert phase_gate.run_phase("morning", catchup_time) == 0
    assert phase_gate.run_phase("morning", catchup_time) == 0
    state = json.loads((tmp_path / "scheduler" / "phase_runs.json").read_text())
    record = state["runs"]["morning:2026-09-21"]
    assert record["delivery_status"] == "catchup"
    assert record["late"] and record["catchup"]
    assert len(runs) == 1


def test_yahoo_regular_close_is_authoritative_over_meta_price():
    calls = []

    def fake_fetch(url, timeout):
        calls.append(url)
        return json.dumps({"chart": {"result": [{
            "meta": {"regularMarketPrice": 999},
            "timestamp": [datetime(2026, 9, 22, 20, tzinfo=timezone.utc).timestamp(), datetime(2026, 9, 23, 20, tzinfo=timezone.utc).timestamp()],
            "indicators": {"quote": [{"close": [100, 101]}]},
        }]}}).encode()

    quote = yahoo_chart_quote("NQ=F", cache=RunCache(), fetcher=fake_fetch)
    assert quote["price"] == 101
    assert quote["prev"] == 100
    assert quote["source"] == "yahoo_regular_ohlc"
    assert len(calls) == 1


def test_run_cache_deduplicates_yahoo_fetches():
    calls = []

    def fake_fetch(url, timeout):
        calls.append(url)
        return json.dumps({"chart": {"result": [{
            "meta": {}, "timestamp": [1, 2],
            "indicators": {"quote": [{"close": [10, 11]}]},
        }]}}).encode()

    cache = RunCache()
    yahoo_chart_quote("^VIX", cache=cache, fetcher=fake_fetch)
    yahoo_chart_quote("^VIX", cache=cache, fetcher=fake_fetch)
    assert len(calls) == 1


def test_oi_baseline_same_session_rerun_does_not_mutate_previous(monkeypatch, tmp_path):
    monkeypatch.setattr(state_store, "STATE_ROOT", tmp_path)
    state_store.commit_oi_close("2026-09-22", {"NVDA": {"total_oi": 100}}, owner="option_flow_close")
    state_store.commit_oi_close("2026-09-23", {"NVDA": {"total_oi": 110}}, owner="option_flow_close")
    state_store.commit_oi_close("2026-09-23", {"NVDA": {"total_oi": 120}}, owner="option_flow_close")
    baseline = state_store.load_oi_baseline("2026-09-23")
    assert baseline["session_date"] == "2026-09-22"
    assert baseline["snapshots"]["NVDA"]["total_oi"] == 100
    stored = json.loads((tmp_path / "option" / "oi_close_snapshot.json").read_text())
    assert stored["previous_snapshots"]["NVDA"]["total_oi"] == 100
    assert stored["snapshots"]["NVDA"]["total_oi"] == 120


def test_legacy_flow_files_migrate_without_losing_oi_universe(monkeypatch, tmp_path):
    monkeypatch.setattr(state_store, "STATE_ROOT", tmp_path / "state")
    monkeypatch.setattr(state_store, "REPO_ROOT", tmp_path)
    (tmp_path / "state").mkdir()
    (tmp_path / "state" / "flow_oi_snapshot.json").write_text(json.dumps({
        "session_date": "2026-09-22",
        "snapshots": {"NVDA": {"call_oi": 12, "put_oi": 8, "total_oi": 20}, "MU": {"call_oi": 5, "put_oi": 3, "total_oi": 8}},
    }))
    (tmp_path / "state" / "flow_signals.json").write_text(json.dumps({"date": "2026-09-22", "signals": [{"ticker": "NVDA"}]}))

    baseline = state_store.load_oi_baseline("2026-09-23")
    signals = state_store.load_flow_signals()

    assert set(baseline["snapshots"]) == {"NVDA", "MU"}
    assert baseline["snapshots"]["NVDA"]["call_oi"] == 12
    assert signals["signals"] == [{"ticker": "NVDA"}]
    assert signals["session_date"] == "2026-09-22"
    assert (tmp_path / "state" / "option" / "flow_signals.json").exists()
    assert not (tmp_path / "state" / "option" / "oi_close_snapshot.json").exists()


def test_oi_baseline_writer_rejects_non_option_flow_owner(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(state_store, "STATE_ROOT", tmp_path)
    with pytest.raises(PermissionError):
        state_store.commit_oi_close("2026-09-23", {}, owner="us_market_report")


def test_state_paths_are_repository_root_state(monkeypatch, tmp_path):
    monkeypatch.setattr(state_store, "STATE_ROOT", tmp_path)
    path = state_store.state_path("report_snapshots", "latest_morning.json")
    state_store.atomic_write_json(path, {"schema_version": 1})
    assert path.parent == tmp_path / "report_snapshots"
    assert not (tmp_path.parent / "scripts" / "report_snapshots").exists()


def test_market_board_has_reference_windows_and_separates_crypto(monkeypatch):
    def fake_quote(symbol, cache):
        return {"symbol": symbol, "price": 1, "change_pct": 2, "source": "yahoo_regular_ohlc",
                "timestamp": "2026-09-23T00:00:00+00:00", "reference_window": "regular_session_daily", "stale": False}

    def fake_crypto(symbol, cache):
        return {"symbol": symbol, "price": 1, "change_pct": 2, "source": "yahoo_crypto",
                "timestamp": "2026-09-23T00:00:00+00:00", "reference_window": "24h", "stale": False}

    monkeypatch.setattr(market_board, "yahoo_chart_quote", fake_quote)
    monkeypatch.setattr(market_board, "_crypto_quote", fake_crypto)
    payload = market_board.collect_market_board()
    assert set(payload["indicators"]) == {"equities", "futures", "rates", "volatility", "fx", "commodities", "crypto"}
    assert payload["indicators"]["crypto"]["btc"]["reference_window"] == "24h"
    assert payload["indicators"]["equities"]["sp500"]["reference_window"] == "regular_session_daily"
    assert "btc" in market_board.ASSETS["crypto"] and "sp500" in market_board.ASSETS["equities"]


def test_snapshot_changes_are_machine_generated():
    current = {"indicators": {"futures": {"nq": {"change_pct": 1.2}}, "volatility": {"vix": {"price": 20}}, "rates": {"us10y": {"price": 4.2}}, "crypto": {"btc": {"change_pct": 3}}}}
    previous = {"indicators": {"futures": {"nq": {"change_pct": 0.7}}, "volatility": {"vix": {"price": 18}}, "rates": {"us10y": {"price": 4.1}}, "crypto": {"btc": {"change_pct": 1}}}}
    changes = compute_changes(current, previous)
    assert changes == {"NQ_change_pct": 0.5, "VIX": 2, "TNX": 0.1, "BTC_24h_change_pct": 2}
