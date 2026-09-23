"""Official-source economic calendar aggregation for R1.

Source adapters are intentionally isolated: an unavailable publisher contributes
an error diagnostic but cannot suppress events from other publishers.
"""
from __future__ import annotations

import hashlib
import re
import urllib.request
from datetime import date, datetime, time, timedelta
from html import unescape
from html.parser import HTMLParser
from typing import Callable

from market_clock import ET, KST

SOURCES = {
    "BLS": ("official_agency", "https://www.bls.gov/schedule/news_release/bls.ics"),
    "BEA": ("official_agency", "https://www.bea.gov/news/schedule"),
    "Census": ("official_agency", "https://www.census.gov/economic-indicators/calendar-listview.html"),
    "Federal Reserve": ("official_agency", "https://www.federalreserve.gov/newsevents/calendar.htm"),
    "EIA": ("official_agency", "https://www.eia.gov/petroleum/supply/weekly/schedule.php"),
    "Treasury": ("official_agency", "https://home.treasury.gov/system/files/221/Tentative-Auction-Schedule.xml"),
    "ISM": ("primary_source", "https://www.ismworld.org/supply-management-news-and-reports/reports/rob-report-calendar/"),
}
_MONTHS = {name.lower(): i for i, name in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.rows = []
        self._row = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in {"br", "p", "div", "li", "td", "th"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag == "tr" and self._row is not None:
            row = " ".join(self._row).strip()
            if row:
                self.rows.append(row)
            self._row = None
        elif tag in {"p", "div", "li", "td", "th"}:
            self.parts.append(" ")

    def handle_data(self, data):
        text = unescape(data).strip()
        if text:
            self.parts.append(text)
            if self._row is not None:
                self._row.append(text)


def _html_text(raw: str) -> tuple[str, list[str]]:
    parser = _Text()
    parser.feed(raw)
    return re.sub(r"\s+", " ", " ".join(parser.parts)), parser.rows


def _fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "MarketBriefingR1/1.0 (official calendar reader)"})
    with urllib.request.urlopen(request, timeout=18) as response:
        return response.read().decode("utf-8-sig", "replace")


def _event(source: str, title: str, when: datetime | None, *, event_type="economic", importance=2,
           scheduled_date: date | None = None) -> dict:
    tier, url = SOURCES[source]
    if when is not None:
        if when.tzinfo is None:
            when = when.replace(tzinfo=ET)
        local = when.astimezone(ET)
        when_iso, kst_iso = local.isoformat(), local.astimezone(KST).isoformat()
        scheduled_date = local.date()
    else:
        when_iso = kst_iso = None
    name = re.sub(r"\s+", " ", title).strip(" -|\t")
    identity_date = (scheduled_date or date.min).isoformat()
    digest = hashlib.sha256(f"{source}|{identity_date}|{event_type}|{name.lower()}".encode()).hexdigest()[:20]
    return {
        "event_id": digest, "source": source, "source_tier": tier, "source_url": url,
        "event_type": event_type, "title": name, "scheduled_at": when_iso,
        "scheduled_at_kst": kst_iso, "importance": importance, "previous": None,
        "forecast": None, "actual": None, "unit": None, "status": "scheduled" if when_iso else "scheduled_date_only",
        "_scheduled_date": identity_date,
    }


def parse_bls_ics(raw: str) -> list[dict]:
    lines = re.sub(r"\r?\n[ \t]", "", raw).splitlines()
    events = []
    props = {}
    for line in lines:
        if line == "BEGIN:VEVENT":
            props = {}
        elif line == "END:VEVENT":
            summary = props.get("SUMMARY", "")
            start_key = next((key for key in props if key.startswith("DTSTART")), None)
            if not summary or not start_key:
                continue
            raw_dt = props[start_key]
            try:
                if "VALUE=DATE" in start_key or re.fullmatch(r"\d{8}", raw_dt):
                    day = datetime.strptime(raw_dt[:8], "%Y%m%d").date()
                    when = None
                else:
                    parsed = datetime.strptime(raw_dt[:15], "%Y%m%dT%H%M%S")
                    tz_match = re.search(r"TZID=([^;:]+)", start_key)
                    if raw_dt.endswith("Z"):
                        from datetime import timezone
                        zone = timezone.utc
                    else:
                        zone = ET if not tz_match or tz_match.group(1) == "America/New_York" else __import__("zoneinfo").ZoneInfo(tz_match.group(1))
                    when = parsed.replace(tzinfo=zone)
                events.append(_event(
                    "BLS", summary.replace(r"\,", ",").replace(r"\;", ";"), when,
                    event_type="labor", scheduled_date=day if when is None else None,
                ))
            except (ValueError, KeyError):
                continue
            props = {}
        elif ":" in line:
            key, value = line.split(":", 1)
            props[key] = value
    return events


_DATE = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,?\s+(\d{4}))?", re.I)
_TIME = re.compile(r"\b(\d{1,2}:\d{2}\s*[AP]M|\d{1,2}\s*[AP]M)\b", re.I)


def _parse_date(match, default_year: int) -> date:
    return date(int(match.group(3) or default_year), _MONTHS[match.group(1).lower()], int(match.group(2)))


def _event_type(title: str) -> str:
    value = title.lower()
    if "gdp" in value or "gross domestic product" in value:
        return "gdp"
    if "international trade" in value or "trade in goods and services" in value:
        return "trade"
    if "fomc" in value or "federal open market" in value:
        return "fomc"
    if "speech" in value or "testimony" in value:
        return "fed_speech"
    if "auction" in value:
        return "treasury_auction"
    if "pmi" in value or "manufacturing" in value or "services" in value:
        return "ism"
    return "economic"


def _events_from_text(source: str, text: str, default_year: int, *, allow_date_only=False) -> list[dict]:
    events = []
    dates = list(_DATE.finditer(text))
    for index, match in enumerate(dates):
        try:
            day = _parse_date(match, default_year)
        except ValueError:
            continue
        end = dates[index + 1].start() if index + 1 < len(dates) else min(len(text), match.end() + 350)
        following = text[match.end():end]
        time_match = _TIME.search(following)
        if not time_match and not allow_date_only:
            continue
        title = following[time_match.end():].strip(" :-|,") if time_match else following.strip(" :-|,")
        title = re.sub(r"^(?:N\s*ews|D\s*ata|Release|Calendar)\s+", "", title, flags=re.I)
        title = title[:180].strip()
        if not title or len(title) < 4:
            continue
        when = None
        if time_match:
            raw_time = time_match.group(1).upper().replace(" ", "")
            fmt = "%I:%M%p" if ":" in raw_time else "%I%p"
            try:
                parsed_time = datetime.strptime(raw_time, fmt).time()
                when = datetime.combine(day, parsed_time, ET)
            except ValueError:
                continue
        events.append(_event(source, title, when, event_type=_event_type(title),
                             importance=3 if _event_type(title) in {"gdp", "trade", "fomc"} else 2,
                             scheduled_date=day))
    return events


def parse_bea_schedule(raw: str, default_year: int) -> list[dict]:
    text, rows = _html_text(raw)
    events = _events_from_text("BEA", text, default_year)
    # BEA schedule cards can run together in the flattened page; row extraction
    # retains each release when the source presents a table.
    if rows:
        events.extend(_events_from_text("BEA", " | ".join(rows), default_year))
    return events


def parse_census_calendar(raw: str, default_year: int) -> list[dict]:
    text, rows = _html_text(raw)
    events = []
    for row in rows:
        match = _DATE.search(row)
        if not match:
            continue
        time_match = _TIME.search(row[match.end():])
        if not time_match:
            continue
        title = row[:match.start()].strip(" |:-")
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            continue
        try:
            day = _parse_date(match, default_year)
            clock = datetime.strptime(time_match.group(1).upper().replace(" ", ""), "%I:%M%p" if ":" in time_match.group(1) else "%I%p").time()
            events.append(_event("Census", title, datetime.combine(day, clock, ET), event_type=_event_type(title),
                                 importance=3 if _event_type(title) in {"trade", "gdp"} else 2))
        except ValueError:
            continue
    if not events:
        events = _events_from_text("Census", text, default_year)
    return events


def parse_fed_calendar(raw: str, default_year: int) -> list[dict]:
    text, rows = _html_text(raw)
    events = []
    for segment in rows or re.split(r"[|;]", text):
        match = _DATE.search(segment)
        if not match or not re.search(r"FOMC|Federal Open Market|speech|testimony|meeting", segment, re.I):
            continue
        try:
            day = _parse_date(match, default_year)
        except ValueError:
            continue
        time_match = _TIME.search(segment)
        when = None
        if time_match:
            try:
                raw_time = time_match.group(1).upper().replace(" ", "")
                parsed_time = datetime.strptime(raw_time, "%I:%M%p" if ":" in raw_time else "%I%p").time()
                when = datetime.combine(day, parsed_time, ET)
            except ValueError:
                continue
        title = re.sub(_DATE, " ", segment, count=1)
        if time_match:
            title = title.replace(time_match.group(0), " ")
        title = re.sub(r"\s+", " ", title).strip(" |:-")[:180]
        if title:
            kind = _event_type(title)
            events.append(_event("Federal Reserve", title, when, event_type=kind,
                                 importance=3 if kind == "fomc" else 2, scheduled_date=day))
    return events


def parse_eia_schedule(raw: str, start: date, end: date) -> list[dict]:
    _, rows = _html_text(raw)
    overrides = {}
    for row in rows:
        if not re.search(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday)\b", row, re.I):
            continue
        dates = list(_DATE.finditer(row))
        if len(dates) < 2:
            continue
        try:
            released = _parse_date(dates[1], start.year)
        except ValueError:
            continue
        clock = _TIME.search(row[dates[1].end():]) or _TIME.search(row)
        if not clock:
            continue
        normalized = clock.group(1).upper().replace(" ", "")
        try:
            parsed = datetime.strptime(normalized, "%I:%M%p" if ":" in normalized else "%I%p").time()
        except ValueError:
            continue
        overrides[released] = parsed
    dates = set()
    cursor = start
    while cursor <= end:
        if cursor.weekday() == 2:
            dates.add(cursor)
        cursor += timedelta(days=1)
    dates.update(day for day in overrides if start <= day <= end)
    # A published alternate release date replaces the usual Wednesday.
    shifted_from = set()
    for released in overrides:
        prior = released - timedelta(days=1)
        if prior.weekday() == 2:
            shifted_from.add(prior)
    events = []
    for day in sorted(dates - shifted_from):
        release_time = overrides.get(day, time(10, 30))
        events.append(_event("EIA", "Weekly Petroleum Status Report (WPSR)", datetime.combine(day, release_time, ET), event_type="energy", importance=3))
    return events


def parse_treasury_schedule(raw: str, default_year: int) -> list[dict]:
    events = []
    for block in re.findall(r"<AuctionCalendarDate>(.*?)</AuctionCalendarDate>", raw, re.S):
        def tag(name):
            match = re.search(rf"<{name}>(.*?)</{name}>", block, re.S)
            return unescape(match.group(1)).strip() if match else ""
        day_text, term, kind = tag("AuctionDate"), tag("SecurityTermWeekYear"), tag("SecurityType")
        try:
            day = date.fromisoformat(day_text)
        except ValueError:
            continue
        title = f"{day.isoformat()} Treasury auction — {term} {kind}".strip()
        events.append(_event("Treasury", title, None, event_type="treasury_auction", importance=2, scheduled_date=day))
    return events


def parse_ism_calendar(raw: str, default_year: int) -> list[dict]:
    text, rows = _html_text(raw)
    candidate = " | ".join(rows) if rows else text
    events = []
    pattern = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\s+(\d{1,2})\s+(\d{1,2})\b", re.I)
    for row in (rows or [candidate]):
        match = pattern.search(row)
        if not match:
            continue
        year, month = int(match.group(2)), _MONTHS[match.group(1).lower()]
        for title, day_num in (("ISM Manufacturing PMI", int(match.group(3))), ("ISM Services PMI", int(match.group(4)))):
            try:
                day = date(year, month, day_num)
            except ValueError:
                continue
            events.append(_event("ISM", title, datetime.combine(day, time(10), ET), event_type="ism", importance=2))
    return events


ADAPTERS = {
    "BLS": lambda raw, start, end: parse_bls_ics(raw),
    "BEA": lambda raw, start, end: parse_bea_schedule(raw, start.year),
    "Census": lambda raw, start, end: parse_census_calendar(raw, start.year),
    "Federal Reserve": lambda raw, start, end: parse_fed_calendar(raw, start.year),
    "EIA": parse_eia_schedule,
    "Treasury": lambda raw, start, end: parse_treasury_schedule(raw, start.year),
    "ISM": lambda raw, start, end: parse_ism_calendar(raw, start.year),
}


def _dedupe_key(event: dict) -> tuple:
    day = event.get("_scheduled_date", "")
    title = event.get("title", "").lower()
    kind = event.get("event_type")
    # BEA and Census can publish the same GDP/trade release; canonicalize title aliases.
    if kind in {"trade", "gdp"}:
        return kind, day
    normalized = re.sub(r"[^a-z0-9]+", " ", title).strip()
    return kind, day, normalized


_TIER_PRIORITY = {"official_agency": 3, "primary_source": 2, "secondary_provider": 1}


def collect_econ_events(start: date, end: date, *, fetcher: Callable[[str], str] | None = None) -> tuple[list[dict], list[str]]:
    """Collect and deduplicate source schedules in an inclusive US-date window."""
    fetcher = fetcher or _fetch
    all_events, errors = [], []
    for source, (_, url) in SOURCES.items():
        try:
            raw = fetcher(url)
            parsed = ADAPTERS[source](raw, start, end)
            for event in parsed:
                day = date.fromisoformat(event["_scheduled_date"])
                if start <= day <= end:
                    all_events.append(event)
        except Exception as error:
            errors.append(f"{source}: {type(error).__name__}: {str(error)[:120]}")
    winners = {}
    for event in all_events:
        key = _dedupe_key(event)
        existing = winners.get(key)
        if existing is None or _TIER_PRIORITY[event["source_tier"]] > _TIER_PRIORITY[existing["source_tier"]]:
            winners[key] = event
    output = []
    for event in winners.values():
        output.append({key: value for key, value in event.items() if not key.startswith("_")})
    output.sort(key=lambda item: (item["scheduled_at"] is None, item["scheduled_at"] or item["title"], item["source"]))
    return output, errors
