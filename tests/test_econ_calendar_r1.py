from datetime import date, datetime

from econ_calendar_r1 import (
    SOURCES,
    collect_econ_events,
    parse_bea_schedule,
    parse_bls_ics,
    parse_census_calendar,
    parse_eia_schedule,
    parse_fed_calendar,
    parse_ism_calendar,
    parse_treasury_schedule,
)
from market_clock import ET, KST, target_us_session_date


def test_schedule_timestamps_are_dst_aware_and_kst_converted():
    summer = parse_bea_schedule(
        "<div>September 23 8:30 AM News U.S. GDP Release</div>", 2026,
    )[0]
    winter = parse_bea_schedule(
        "<div>January 23 8:30 AM News U.S. GDP Release</div>", 2026,
    )[0]
    assert summer["scheduled_at"].endswith("-04:00")
    assert summer["scheduled_at_kst"].endswith("+09:00")
    assert "21:30" in summer["scheduled_at_kst"]
    assert winter["scheduled_at"].endswith("-05:00")
    assert "22:30" in winter["scheduled_at_kst"]
    assert summer["forecast"] is None


def test_bls_ics_preserves_source_timezone_and_does_not_invent_time():
    fixture = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART;VALUE=DATE;TZID=America/New_York:20260923T083000
SUMMARY:Employment Situation
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=America/New_York:20260924
SUMMARY:Employment Situation day marker
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260925T123000Z
SUMMARY:Hybrid UTC timestamp
END:VEVENT
END:VCALENDAR"""
    events = parse_bls_ics(fixture)
    assert events[0]["scheduled_at"].endswith("-04:00")
    assert events[1]["scheduled_at"] is None
    assert events[1]["status"] == "scheduled_date_only"
    assert events[1]["scheduled_date"] == "2026-09-24"
    assert events[2]["scheduled_at"].endswith("-04:00")
    assert events[2]["scheduled_at_kst"].endswith("+09:00")
    assert "08:30:00" in events[2]["scheduled_at"]


def test_yearless_schedule_dates_resolve_to_years_inside_requested_window():
    fixture = "<div>December 31 8:30 AM News Year-end event January 1 8:30 AM News New Year event</div>"
    events = parse_bea_schedule(fixture, 2026, date(2026, 12, 31), date(2027, 1, 1))
    assert [event["scheduled_date"] for event in events] == ["2026-12-31", "2027-01-01"]
    assert all(event["scheduled_date"] is not None for event in events)


def test_kst_date_rollover_resolves_target_us_session():
    before_midnight_et = datetime(2026, 9, 23, 6, 30, tzinfo=KST)
    after_midnight_et = datetime(2026, 9, 24, 6, 30, tzinfo=KST)
    assert target_us_session_date("morning", before_midnight_et) == date(2026, 9, 22)
    assert target_us_session_date("morning", after_midnight_et) == date(2026, 9, 23)


def test_eia_holiday_adjusted_release_uses_official_alternate_date_and_time():
    fixture = """<table><tr><td>Week ending</td><td>Alternate release date</td><td>Release day</td><td>Release time</td></tr>
    <tr><td>September 4, 2026</td><td>September 10, 2026</td><td>Thursday</td><td>12:00 PM</td><td>Labor Day</td></tr></table>"""
    events = parse_eia_schedule(fixture, date(2026, 9, 9), date(2026, 9, 10))
    assert len(events) == 1
    assert "2026-09-10T12:00:00-04:00" == events[0]["scheduled_at"]
    assert events[0]["source"] == "EIA"


def test_bea_and_census_duplicate_trade_event_prefers_first_official_source():
    bea = "<div>September 24 8:30 AM News U.S. International Trade in Goods and Services</div>"
    census = "<table><tr><td>U.S. International Trade in Goods and Services</td><td>September 24, 2026</td><td>8:30 AM</td></tr></table>"
    docs = {SOURCES["BEA"][1]: bea, SOURCES["Census"][1]: census}
    events, _errors = collect_econ_events(
        date(2026, 9, 24), date(2026, 9, 24), fetcher=lambda url: docs[url],
    )
    trade = [event for event in events if event["event_type"] == "trade"]
    assert len(trade) == 1
    assert trade[0]["source"] == "BEA"
    assert set(trade[0]) == {
        "event_id", "source", "source_tier", "source_url", "event_type", "title",
        "scheduled_at", "scheduled_at_kst", "scheduled_date", "importance", "previous", "forecast",
        "actual", "unit", "status",
    }


def test_federal_reserve_speeches_and_fomc_are_included():
    fixture = """<table>
      <tr><td>September 23, 2026</td><td>Speech by Governor Example</td><td>1:00 PM</td></tr>
      <tr><td>September 24, 2026</td><td>FOMC meeting</td><td>2:00 PM</td></tr>
    </table>"""
    events = parse_fed_calendar(fixture, 2026)
    assert any(event["event_type"] == "fed_speech" for event in events)
    assert any(event["event_type"] == "fomc" for event in events)


def test_ism_official_calendar_and_treasury_date_only_schedule():
    ism = parse_ism_calendar("<table><tr><td>September 2026</td><td>1</td><td>3</td></tr></table>", 2026)
    assert [(e["title"], e["scheduled_at"]) for e in ism] == [
        ("ISM Manufacturing PMI", "2026-09-01T10:00:00-04:00"),
        ("ISM Services PMI", "2026-09-03T10:00:00-04:00"),
    ]
    xml = """<AuctionCalendar><AuctionCalendarDate><SecurityTermWeekYear>10-Year</SecurityTermWeekYear>
      <SecurityType>NOTE</SecurityType><AuctionDate>2026-09-23</AuctionDate></AuctionCalendarDate></AuctionCalendar>"""
    auction = parse_treasury_schedule(xml, 2026)[0]
    assert auction["scheduled_at"] is None
    assert auction["scheduled_at_kst"] is None
    assert "2026-09-23" in auction["title"]


def test_calendar_source_failure_isolated_and_morning_artifact_has_fixture_event(monkeypatch):
    docs = {SOURCES["BEA"][1]: "<div>September 23 8:30 AM News Personal Income and Outlays</div>"}
    def fetch(url):
        if url in docs:
            return docs[url]
        raise OSError("fixture source unavailable")

    events, errors = collect_econ_events(date(2026, 9, 23), date(2026, 9, 24), fetcher=fetch)
    assert events and events[0]["source"] == "BEA"
    assert len(errors) == len(SOURCES) - 1

    import morning_delivery
    requested_window = []
    def collect_for_window(start, end):
        requested_window.append((start, end))
        return events, errors
    monkeypatch.setattr(morning_delivery, "collect_econ_events", collect_for_window)
    monkeypatch.setattr(morning_delivery, "collect_market_board", lambda cache: {"indicators": {}, "data_quality": []})
    monkeypatch.setattr(morning_delivery, "collect_news", lambda: [])
    monkeypatch.setattr(morning_delivery, "collect_earnings", lambda session: [])
    payload = morning_delivery.build_morning_payload(datetime(2026, 9, 23, 6, 30, tzinfo=KST))
    assert requested_window == [(date(2026, 9, 23), date(2026, 9, 23))]
    telegram = "\n".join(morning_delivery.render_telegram_compact(payload))
    assert "Personal Income and Outlays" in telegram
    assert "21:30 KST" in telegram
