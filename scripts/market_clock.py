"""DST-aware US market clock shared by every report entrypoint."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
UTC = ZoneInfo("UTC")

REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def us_market_holidays(year: int) -> set[date]:
    """Return the weekday closures relevant to regular US equity sessions."""
    holidays = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),       # MLK
        _nth_weekday(year, 2, 0, 3),       # Presidents' Day
        _last_weekday(year, 5, 0),          # Memorial Day
        _observed(date(year, 6, 19)),       # Juneteenth
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),        # Labor Day
        _nth_weekday(year, 11, 3, 4),       # Thanksgiving
        _observed(date(year, 12, 25)),
    }
    # If next year's Jan 1 is Saturday, its observed Friday falls on Dec 31
    # of this year and must be included when evaluating this year's sessions.
    next_new_year_observed = _observed(date(year + 1, 1, 1))
    if next_new_year_observed.year == year:
        holidays.add(next_new_year_observed)
    # Good Friday is the only non-weekend movable full-day closure here.
    easter = _easter_sunday(year)
    holidays.add(easter - timedelta(days=2))
    return holidays


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm.
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def is_regular_session_day(day: date) -> bool:
    return day.weekday() < 5 and day not in us_market_holidays(day.year)


def previous_regular_session(day: date, include_day: bool = False) -> date:
    candidate = day if include_day else day - timedelta(days=1)
    while not is_regular_session_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def next_regular_session(day: date, include_day: bool = False) -> date:
    candidate = day if include_day else day + timedelta(days=1)
    while not is_regular_session_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def now_et(now: Optional[datetime] = None) -> datetime:
    return (now or datetime.now(tz=UTC)).astimezone(ET)


def now_kst(now: Optional[datetime] = None) -> datetime:
    return (now or datetime.now(tz=UTC)).astimezone(KST)


def infer_phase(now: Optional[datetime] = None) -> str:
    """Infer the four report windows from KST without hard-coded ET offsets."""
    local = now_kst(now).time()
    if time(4, 30) <= local < time(6, 30):
        return "close"
    if time(6, 30) <= local < time(12, 0):
        return "morning"
    if time(20, 0) <= local < time(22, 45):
        return "evening"
    if local >= time(22, 45) or local < time(1, 30):
        return "open"
    return "off_hours"


def target_us_session_date(phase: str, now: Optional[datetime] = None) -> date:
    """Resolve the US calendar date a report is talking about.

    Morning/close describe the most recent completed US session. Evening/open
    describe the upcoming/current US session, even when KST has crossed midnight.
    """
    et = now_et(now)
    if phase in {"morning", "close"}:
        return previous_regular_session(et.date(), include_day=is_regular_session_day(et.date()))
    if phase in {"evening", "open"}:
        return next_regular_session(et.date(), include_day=True)
    return previous_regular_session(et.date(), include_day=is_regular_session_day(et.date()))


def last_actual_regular_session(now: Optional[datetime] = None) -> date:
    et = now_et(now)
    include = is_regular_session_day(et.date()) and et.time() >= REGULAR_CLOSE
    return previous_regular_session(et.date(), include_day=include)


@dataclass(frozen=True)
class MarketClock:
    now_et: datetime
    now_kst: datetime
    market_session_date: date
    last_regular_session: date
    phase: str

    def as_dict(self) -> dict:
        return {
            "now_et": self.now_et.isoformat(),
            "now_kst": self.now_kst.isoformat(),
            "market_session_date": self.market_session_date.isoformat(),
            "last_regular_session": self.last_regular_session.isoformat(),
            "phase": self.phase,
        }


def get_market_clock(phase: Optional[str] = None, now: Optional[datetime] = None) -> MarketClock:
    et = now_et(now)
    kst = now_kst(now)
    actual_phase = phase or infer_phase(now)
    return MarketClock(
        now_et=et,
        now_kst=kst,
        market_session_date=target_us_session_date(actual_phase, now),
        last_regular_session=last_actual_regular_session(now),
        phase=actual_phase,
    )
