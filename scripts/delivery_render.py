"""Render one canonical morning payload into Email Full and Telegram Compact."""

from __future__ import annotations

import html
import re
from typing import Iterable


def _num(value, digits=2):
    if not isinstance(value, (int, float)):
        return "-"
    return f"{value:,.{digits}f}"


def _pct(value, digits=2, suffix="%"):
    if not isinstance(value, (int, float)):
        return "-"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{digits}f}{suffix}"


def _price(value):
    if not isinstance(value, (int, float)):
        return "-"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:,.2f}"
    return f"{value:,.2f}"


def _quote(indicators: dict, category: str, key: str) -> dict:
    value = indicators.get(category, {}).get(key, {})
    return value if isinstance(value, dict) else {}


def _change(q: dict) -> str:
    return _pct(q.get("change_pct"))


def _yield_line(q: dict) -> str:
    price = q.get("price")
    change = q.get("change")
    if not isinstance(price, (int, float)):
        return "10Y -"
    bp = change * 100 if isinstance(change, (int, float)) else None
    bp_text = "-" if bp is None else f"{bp:+.0f}bp"
    return f"10Y {price:.3f}% ({bp_text})"


def market_board_lines(payload: dict) -> list[str]:
    indicators = payload.get("indicators", {})
    sp = _quote(indicators, "equities", "sp500")
    nasdaq = _quote(indicators, "equities", "nasdaq_composite")
    russell = _quote(indicators, "equities", "russell_2000")
    soxx = _quote(indicators, "equities", "soxx")
    tnx = _quote(indicators, "rates", "us10y")
    vix = _quote(indicators, "volatility", "vix")
    dxy = _quote(indicators, "fx", "dxy")
    wti = _quote(indicators, "commodities", "wti")
    gold = _quote(indicators, "commodities", "gold_futures")
    silver = _quote(indicators, "commodities", "silver_futures")
    btc = _quote(indicators, "crypto", "btc")
    eth = _quote(indicators, "crypto", "eth")
    es = _quote(indicators, "futures", "es")
    nq = _quote(indicators, "futures", "nq")
    rty = _quote(indicators, "futures", "rty")

    return [
        f"주식 S&P {_change(sp)} | Nasdaq {_change(nasdaq)} | Russell {_change(russell)} | SOXX {_change(soxx)}",
        f"금리/변동 {_yield_line(tnx)} | VIX {_price(vix.get('price'))} ({_change(vix)}) | DXY {_price(dxy.get('price'))} ({_change(dxy)})",
        f"원자재 WTI ${_price(wti.get('price'))} ({_change(wti)}) | Gold ${_price(gold.get('price'))} ({_change(gold)}) | Silver ${_price(silver.get('price'))} ({_change(silver)})",
        f"크립토 BTC ${_price(btc.get('price'))} ({_change(btc)} 24h) | ETH ${_price(eth.get('price'))} ({_change(eth)} 24h)",
        f"선물 ES {_change(es)} | NQ {_change(nq)} | RTY {_change(rty)}",
    ]


def _market_summary(payload: dict) -> list[str]:
    indicators = payload.get("indicators", {})
    keys = [
        ("S&P", _quote(indicators, "equities", "sp500")),
        ("Nasdaq", _quote(indicators, "equities", "nasdaq_composite")),
        ("Russell", _quote(indicators, "equities", "russell_2000")),
        ("SOXX", _quote(indicators, "equities", "soxx")),
    ]
    valid = [(name, q.get("change_pct")) for name, q in keys if isinstance(q.get("change_pct"), (int, float))]
    notes = []
    if valid:
        positives = sum(1 for _, value in valid if value > 0)
        negatives = sum(1 for _, value in valid if value < 0)
        if positives == len(valid):
            notes.append("주요 지수가 전반적으로 상승했습니다.")
        elif negatives == len(valid):
            notes.append("주요 지수가 전반적으로 약세였습니다.")
        else:
            notes.append("주요 지수 흐름은 혼조였습니다.")
        leader = max(valid, key=lambda item: item[1])
        laggard = min(valid, key=lambda item: item[1])
        if leader[1] - laggard[1] >= 0.7:
            notes.append(f"{leader[0]}가 상대적으로 강했고 {laggard[0]}가 가장 약해 지수 간 차별화가 컸습니다.")
    vix = _quote(indicators, "volatility", "vix")
    vix_change = vix.get("change_pct")
    if isinstance(vix_change, (int, float)):
        if vix_change >= 5:
            notes.append("VIX가 빠르게 올라 위험 프리미엄이 확대되는 방향입니다.")
        elif vix_change <= -5:
            notes.append("VIX가 크게 내려 단기 위험 프리미엄은 완화되는 방향입니다.")
    return notes[:3]


def _importance(value) -> str:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return ""
    return "★" * max(1, min(value, 3))


def _clean_items(items: Iterable[dict]) -> list[dict]:
    return [item for item in items if isinstance(item, dict) and not item.get("error")]


def _econ_lines(payload: dict, limit: int | None = None) -> list[str]:
    items = _clean_items(payload.get("econ_calendar", []))
    if limit is not None:
        high = [item for item in items if int(item.get("importance") or 0) >= 2]
        items = high[:limit]
    lines = []
    for item in items:
        values = []
        if item.get("forecast") not in (None, ""):
            values.append(f"예상 {item['forecast']}")
        if item.get("previous") not in (None, ""):
            values.append(f"이전 {item['previous']}")
        if item.get("actual") not in (None, ""):
            values.append(f"실제 {item['actual']}")
        suffix = f" | {' / '.join(values)}" if values else ""
        scheduled = item.get("scheduled_at_kst")
        time_text = item.get("time")
        date_only = False
        if scheduled:
            try:
                from datetime import datetime
                time_text = datetime.fromisoformat(scheduled).strftime("%m-%d %H:%M")
            except (TypeError, ValueError):
                pass
        title = item.get("title") or item.get("event") or "-"
        if not scheduled and item.get("status") == "scheduled_date_only":
            match = re.match(r"(\d{4}-\d{2}-\d{2})\s+", title)
            if match:
                time_text = f"{match.group(1)} ET date (time TBA)"
                title = title[match.end():]
                date_only = True
        zone_label = "" if date_only else " KST"
        lines.append(f"{time_text or '-'}{zone_label} | {title} {_importance(item.get('importance'))}{suffix}")
    return lines


def _earnings_lines(payload: dict, limit: int | None = None) -> list[str]:
    items = _clean_items(payload.get("earnings", []))
    if limit is not None:
        items = items[:limit]
    lines = []
    for item in items:
        window = (item.get("time") or "시간 미정").replace("pre-market", "장전").replace("after-hours", "장후")
        eps = item.get("eps_forecast")
        eps_text = f" | EPS 예상 {eps}" if eps not in (None, "") else ""
        lines.append(f"{item.get('symbol') or '-'} {item.get('name') or ''} | {window}{eps_text}".strip())
    return lines


CORE_OPTION_WATCHLIST = (
    "NVDA", "AMD", "MU", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA",
    "AVGO", "TSM", "INTC", "QCOM", "ARM", "ASML", "LRCX", "AMAT", "KLAC",
    "MRVL", "SMCI", "COIN", "HOOD", "PLTR", "SPY", "QQQ",
)


def rank_option_symbols(payload: dict, limit: int = 8) -> list[str]:
    """Rank actual signals first, then core coverage, then OI/IV evidence."""
    options = payload.get("options") or {}
    if not isinstance(options, dict):
        return []
    signals = payload.get("current_flow_signals") or payload.get("signals") or []
    anomalies = payload.get("oi_anomalies") or []
    signal_order = {}
    for records in (signals, anomalies):
        for record in records if isinstance(records, list) else []:
            if not isinstance(record, dict):
                continue
            ticker = record.get("ticker") or record.get("symbol")
            if ticker:
                signal_order.setdefault(str(ticker).upper(), len(signal_order))
    for ticker, item in options.items():
        if isinstance(item, dict) and (item.get("signal") or item.get("anomaly") or item.get("is_anomaly")):
            signal_order.setdefault(str(ticker).upper(), len(signal_order))

    watch_order = {ticker: index for index, ticker in enumerate(CORE_OPTION_WATCHLIST)}
    valid = {
        str(ticker).upper(): item for ticker, item in options.items()
        if isinstance(item, dict) and not item.get("error")
    }

    def score(ticker: str):
        item = valid[ticker]
        oi_delta = item.get("oi_change")
        try:
            oi_magnitude = abs(float(oi_delta))
        except (TypeError, ValueError):
            oi_magnitude = -1.0
        iv = item.get("iv30")
        iv_valid = isinstance(iv, (int, float)) and iv > 0
        total_oi = item.get("total_oi")
        try:
            total = float(total_oi)
        except (TypeError, ValueError):
            total = -1.0
        return (
            0 if ticker in signal_order else 1,
            signal_order.get(ticker, 0) if ticker in signal_order else 0,
            0 if ticker in watch_order else 1,
            watch_order.get(ticker, 0) if ticker in watch_order else 0,
            -oi_magnitude,
            0 if iv_valid else 1,
            -float(iv) if iv_valid else 0.0,
            -total,
        )

    ranked = sorted(valid, key=score)
    return ranked[:max(0, min(limit, 8))]


def _option_lines(payload: dict, limit: int = 8) -> list[str]:
    lines = []
    options = payload.get("options") or {}
    for symbol in rank_option_symbols(payload, limit):
        item = options.get(symbol) or options.get(symbol.lower())
        if not isinstance(item, dict):
            continue
        iv = _pct((item.get("iv30") or 0) * 100, 1) if isinstance(item.get("iv30"), (int, float)) else "-"
        oi_change = item.get("oi_change")
        lines.append(
            f"{symbol} | IV30 {iv} | OI {item.get('total_oi', '-')} | OI Δ {oi_change if oi_change is not None else '-'}"
        )
    return lines


def _news_lines(payload: dict, limit: int = 5) -> list[str]:
    items = _clean_items(payload.get("news", []))[:limit]
    lines = []
    for item in items:
        title = item.get("title_ko") or item.get("title") or "-"
        when = item.get("time") or ""
        lines.append(f"{when} {title}".strip())
    return lines


def render_telegram_compact(payload: dict, max_chars: int = 3500) -> list[str]:
    meta = payload.get("delivery", {})
    date_text = meta.get("delivery_date") or payload.get("session_date") or "-"
    mode = meta.get("mode", "close_autopsy")
    mode_label = "주간 시작" if mode == "week_kickoff" else "모닝"
    lines = [
        f"☀️ 미국증시 {mode_label} | {date_text} 06:30 KST",
        "",
        "📊 주요 지표",
        *market_board_lines(payload),
    ]
    summary = _market_summary(payload)
    if summary:
        lines += ["", "🧭 핵심 해석", *[f"• {item}" for item in summary]]

    news = _news_lines(payload, 3)
    if news:
        lines += ["", "📰 뉴스 TOP3", *[f"• {item}" for item in news]]

    econ = _econ_lines(payload, 6)
    if econ:
        lines += ["", "🗓 오늘 일정 (KST)", *econ]
    elif payload.get("econ_calendar"):
        lines += ["", "🗓 오늘 일정 (KST)", "• 경제 캘린더 소스 확인 필요"]

    earnings = _earnings_lines(payload, 5)
    if earnings:
        lines += ["", "🏢 주요 실적", *[f"• {item}" for item in earnings]]

    lines += ["", "상세 뉴스·전체 캘린더·옵션 해설 → 이메일 뉴스레터"]
    text = "\n".join(lines).strip()
    if len(text) <= max_chars:
        return [text]

    # Split at section boundaries while staying comfortably under Telegram's hard limit.
    sections = text.split("\n\n")
    chunks, current = [], ""
    for section in sections:
        candidate = section if not current else current + "\n\n" + section
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = section
    if current:
        chunks.append(current)
    return chunks


def render_email_full(payload: dict) -> tuple[str, str, str]:
    meta = payload.get("delivery", {})
    date_text = meta.get("delivery_date") or payload.get("session_date") or "-"
    mode = meta.get("mode", "close_autopsy")
    mode_label = "Week Kickoff" if mode == "week_kickoff" else "Close Autopsy"
    subject = f"[미국증시 모닝] {mode_label} | {date_text} 06:30 KST"

    parts = [
        f"미국증시 모닝 뉴스레터 — {date_text} 06:30 KST",
        f"모드: {mode_label}",
        "",
        "■ 30초 요약",
        *(_market_summary(payload) or ["시장 요약 데이터가 충분하지 않습니다."]),
        "",
        "■ 주요 지표",
        *market_board_lines(payload),
    ]

    news = _news_lines(payload, 7)
    parts += ["", "■ 주요 뉴스"]
    parts += [f"- {line}" for line in news] if news else ["- 주요 뉴스 없음/수집 오류"]

    econ = _econ_lines(payload)
    parts += ["", "■ 오늘 경제 캘린더 — KST"]
    parts += [f"- {line}" for line in econ] if econ else ["- 경제 캘린더 데이터 없음 또는 소스 오류"]

    earnings = _earnings_lines(payload)
    parts += ["", "■ 오늘 주요 실적"]
    parts += [f"- {line}" for line in earnings] if earnings else ["- 주요 실적 데이터 없음"]

    options = _option_lines(payload)
    if options:
        parts += ["", "■ 옵션 / OI"]
        parts.extend(f"- {line}" for line in options)

    quality = payload.get("data_quality") or []
    if quality:
        parts += ["", "■ 데이터 품질", *[f"- {item}" for item in quality]]

    parts += ["", "※ 수치는 동일 canonical snapshot에서 생성됩니다. Sigma/News Intelligence가 추가되면 해설이 더 깊어집니다."]
    plain = "\n".join(parts).strip()

    html_sections = [
        f"<h1>미국증시 모닝 뉴스레터</h1><p><strong>{html.escape(date_text)} 06:30 KST</strong> · {html.escape(mode_label)}</p>",
        "<h2>30초 요약</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in (_market_summary(payload) or ["시장 요약 데이터가 충분하지 않습니다."])) + "</ul>",
        "<h2>주요 지표</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in market_board_lines(payload)) + "</ul>",
        "<h2>주요 뉴스</h2><ul>" + ("".join(f"<li>{html.escape(item)}</li>" for item in news) if news else "<li>주요 뉴스 없음/수집 오류</li>") + "</ul>",
        "<h2>오늘 경제 캘린더 — KST</h2><ul>" + ("".join(f"<li>{html.escape(item)}</li>" for item in econ) if econ else "<li>경제 캘린더 데이터 없음 또는 소스 오류</li>") + "</ul>",
        "<h2>오늘 주요 실적</h2><ul>" + ("".join(f"<li>{html.escape(item)}</li>" for item in earnings) if earnings else "<li>주요 실적 데이터 없음</li>") + "</ul>",
    ]
    if options:
        html_sections.append("<h2>옵션 / OI</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in options) + "</ul>")
    if quality:
        html_sections.append("<h2>데이터 품질</h2><ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in quality) + "</ul>")
    html_body = "<html><body style=\"font-family:Arial,sans-serif;line-height:1.55\">" + "".join(html_sections) + "<p><small>동일 canonical snapshot 기반. Sigma/News Intelligence 통합 후 해설 강화 예정.</small></p></body></html>"
    return subject, plain, html_body
