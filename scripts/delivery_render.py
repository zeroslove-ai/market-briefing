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
    insight = payload.get("insight") or {}
    items = _clean_items(insight.get("economic_events") or payload.get("econ_calendar", []))
    if limit is not None:
        high = [item for item in items if int(item.get("contextual_importance", item.get("importance")) or 0) >= 2]
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
            date_value = item.get("scheduled_date")
            if date_value:
                try:
                    from datetime import date
                    parsed_date = date.fromisoformat(date_value)
                    title = re.sub(r"^\d{4}-\d{2}-\d{2}\s+", "", title)
                    time_text = f"{parsed_date.month}/{parsed_date.day} — {title}"
                    date_only = True
                except (TypeError, ValueError):
                    pass
            if not date_only:
                match = re.match(r"(\d{4})-(\d{2})-(\d{2})\s+", title)
                if match:
                    time_text = f"{int(match.group(2))}/{int(match.group(3))} — {title[match.end():]}"
                    date_only = True
        zone_label = "" if date_only else " KST"
        if date_only:
            importance = item.get("contextual_importance", item.get("importance"))
            line = f"{time_text} {_importance(importance)}{suffix}"
            context = item.get("why_today_matters")
            if context:
                line += f" — {context}"
            lines.append(line)
        else:
            importance = item.get("contextual_importance", item.get("importance"))
            context = item.get("why_today_matters")
            line = f"{time_text or '-'}{zone_label} | {title} {_importance(importance)}{suffix}"
            if context:
                line += f" — {context}"
            lines.append(line)
    return lines


def _earnings_lines(payload: dict, limit: int | None = None) -> list[str]:
    insight_earnings = (payload.get("insight") or {}).get("earnings") or {}
    items = _clean_items(insight_earnings.get("top") or payload.get("earnings", []))
    if limit is not None:
        items = items[:limit]
    lines = []
    for item in items:
        window = (item.get("time") or "시간 미정").replace("pre-market", "장전").replace("after-hours", "장후")
        eps = item.get("eps_forecast")
        eps_text = f" | EPS 예상 {eps}" if eps not in (None, "") else ""
        checkpoints = item.get("what_to_watch") or ["매출 성장", "마진·가이던스"]
        line = f"{item.get('symbol') or '-'} {item.get('name') or ''} | {window}{eps_text} | 체크: {' / '.join(checkpoints[:3])}".strip()
        lines.append(line)
    other_count = insight_earnings.get("other_count", 0)
    if other_count:
        lines.append(f"기타 실적 {other_count}개")
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
    insight = payload.get("insight") or {}
    clusters = insight.get("story_clusters") or []
    if clusters:
        items = clusters[:limit]
        return [
            f"{item.get('what_happened', '-')} — {item.get('why_it_matters', '')} 반응: {item.get('market_reaction', '')} 다음: {item.get('what_to_watch', '')}"
            for item in items
        ]
    items = _clean_items(payload.get("news", []))[:limit]
    lines = []
    for item in items:
        title = item.get("title_ko") or item.get("title") or "-"
        when = item.get("time") or ""
        lines.append(f"{when} {title}".strip())
    return lines


def _safe_quality(payload: dict) -> list[str]:
    if not payload.get("data_quality"):
        return []
    return ["일부 공식 소스 지연; 대체 소스로 일정을 확인했습니다."]


def _claim_lines(payload: dict, limit: int = 5) -> list[str]:
    insight = payload.get("insight") or {}
    names = insight.get("claim_summaries") or insight.get("market_movers") or []
    if names:
        return names[:limit]
    return _market_summary(payload)[:limit]


def _map_lines(payload: dict) -> list[str]:
    insight = payload.get("insight") or {}
    rows = insight.get("market_map") or []
    if rows:
        return [f"{row['metric']} {row['value']} — {row['interpretation']}" for row in rows]
    return market_board_lines(payload)


def render_telegram_compact(payload: dict, max_chars: int = 2500) -> list[str]:
    meta = payload.get("delivery", {})
    date_text = meta.get("delivery_date") or payload.get("session_date") or "-"
    mode = meta.get("mode", "close_autopsy")
    mode_label = "주간 시작" if mode == "week_kickoff" else "모닝"
    lines = [
        f"☀️ 미국증시 {mode_label} | {date_text} 06:30 KST",
        "",
        f"🧭 {((payload.get('insight') or {}).get('conclusion') or '주요 자산의 흐름을 확인합니다.')}",
        "",
        "📊 Market Map",
        *_map_lines(payload)[:10],
    ]
    summary = _claim_lines(payload, 4)
    if summary:
        lines += ["", "🔎 왜 중요한가", *[f"• {item}" for item in summary]]

    news = _news_lines(payload, 3)
    if news:
        lines += ["", "📰 관련 스토리", *[f"• {item}" for item in news[:3]]]

    econ = _econ_lines(payload, 6)
    if econ:
        lines += ["", "🗓 오늘 일정 (KST)", *econ]
    elif payload.get("econ_calendar"):
        lines += ["", "🗓 오늘 일정 (KST)", "• 경제 캘린더 소스 확인 필요"]

    earnings = _earnings_lines(payload, 5)
    if earnings:
        lines += ["", "🏢 주요 실적", *[f"• {item}" for item in earnings]]

    watch = ((payload.get("insight") or {}).get("what_to_watch") or [])[:3]
    if watch:
        lines += ["", "🎯 오늘 확인할 것", *[f"• {item}" for item in watch]]
    quality = _safe_quality(payload)
    if quality:
        lines += ["", *quality]
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
    insight = payload.get("insight") or {}
    conclusion = insight.get("conclusion") or "시장 흐름은 혼조이며 뚜렷한 단일 주도 요인은 확인되지 않았습니다."
    short_conclusion = insight.get("subject_conclusion") or conclusion.split("。")[0].split(". ")[0][:62]
    day = date_text[5:7].lstrip("0") + "/" + date_text[8:10].lstrip("0") if len(date_text) >= 10 else date_text
    subject = f"[미국증시 모닝] {short_conclusion} | {day} 06:30 KST"

    parts = [f"미국증시 모닝 뉴스레터 — {date_text} 06:30 KST", f"모드: {mode_label}", "",
             "■ 오늘 시장 한 문장", conclusion, "",
             "■ 30초 핵심"]
    summary = insight.get("market_movers") or _market_summary(payload)
    parts.extend(f"- {item}" for item in summary[:6] or ["시장 요약 데이터가 충분하지 않습니다."])
    parts += ["", "■ Market Map"]
    parts.extend(f"- {line}" for line in _map_lines(payload))

    claims = insight.get("market_driver_claims") or insight.get("claims", [])
    if claims:
        parts += ["", "■ 오늘 시장을 움직인 3가지"]
        for claim in claims[:3]:
            label = claim.get("claim_id", "").replace("_", " ").title()
            parts.append(f"- {label} ({claim.get('confidence', 'LOW')}): {claim.get('support', [''])[0]}")
            if claim.get("counter_evidence"):
                parts.append(f"  반대 근거: {claim['counter_evidence'][0]}")
            parts.append(f"  확인할 것: {claim.get('what_to_watch', '')}")

    news = _news_lines(payload, 5)
    parts += ["", "■ Top Story Clusters"]
    clusters = insight.get("story_clusters") or []
    if clusters:
        for item in clusters:
            sources = "; ".join(f"{s.get('source') or '기사'}: {s.get('url')}" for s in item.get("sources", []) if s.get("url"))
            parts += [f"- {item.get('what_happened')}", f"  왜 중요한가: {item.get('why_it_matters')}",
                      f"  시장 반응: {item.get('market_reaction')}", f"  반대 근거: {item.get('counter_evidence')}",
                      f"  다음 확인: {item.get('what_to_watch')}"]
            if sources:
                parts.append(f"  출처: {sources}")
    else:
        parts.extend(f"- {line}" for line in news or ["관련 스토리 자료 없음; 추가 조사가 필요합니다."])

    econ = _econ_lines(payload)
    parts += ["", "■ 경제일정 — 왜 오늘 중요한지"]
    parts.extend(f"- {line}" for line in econ) if econ else parts.append("- 경제 일정 자료 없음")

    earnings = _earnings_lines(payload, 5)
    parts += ["", "■ 주요 실적 — 관전 포인트"]
    parts.extend(f"- {line}" for line in earnings) if earnings else parts.append("- 주요 실적 데이터 없음")

    options = _option_lines(payload)
    if options:
        parts += ["", "■ 옵션 / OI"]
        parts.extend(f"- {line}" for line in options)

    quality = _safe_quality(payload)

    watch = insight.get("what_to_watch") or []
    if watch:
        parts += ["", "■ 오늘 확인할 것"]
        parts.extend(f"- {index}. {item}" for index, item in enumerate(watch[:5], 1))
    research = insight.get("research_needed")
    if research:
        parts.append("※ 큰 움직임의 원인에 대한 외부 심층 확인은 조사 대기 중이며, 인과는 확정하지 않았습니다.")
    parts += ["", "※ 수치와 파생 feature는 같은 canonical snapshot에서 계산됩니다. 원인 해석은 근거와 함께 구분합니다."]
    if quality:
        parts += ["", "■ 데이터 품질", *[f"- {item}" for item in quality]]
    plain = "\n".join(parts).strip()

    html_sections = [
        f"<h1>미국증시 모닝 뉴스레터</h1><p><strong>{html.escape(date_text)} 06:30 KST</strong> · {html.escape(mode_label)}</p>",
        f"<h2>오늘 시장 한 문장</h2><p>{html.escape(conclusion)}</p>",
        "<h2>30초 핵심</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in summary[:6]) + "</ul>",
        "<h2>Market Map</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in _map_lines(payload)) + "</ul>",
    ]
    if claims:
        html_sections.append("<h2>오늘 시장을 움직인 3가지</h2><ul>" + "".join(
            f"<li>{html.escape(claim.get('claim_id', '').replace('_', ' ').title())} ({html.escape(claim.get('confidence', 'LOW'))}): "
            f"{html.escape(str((claim.get('support') or [''])[0]))}<br><small>반대 근거: "
            f"{html.escape(str((claim.get('counter_evidence') or ['없음'])[0]))} · 확인할 것: "
            f"{html.escape(claim.get('what_to_watch', ''))}</small></li>" for claim in claims[:3]
        ) + "</ul>")
    if clusters:
        story_html = []
        for item in clusters:
            source_links = []
            for source in item.get("sources", []):
                url = source.get("url")
                if url:
                    label = html.escape(source.get("source") or source.get("title") or "출처")
                    source_links.append(f'<a href="{html.escape(url, quote=True)}">{label}</a>')
            story_html.append(
                f"<li><strong>{html.escape(item.get('what_happened', '-'))}</strong><br>"
                f"왜 중요한가: {html.escape(item.get('why_it_matters', ''))}<br>"
                f"시장 반응: {html.escape(item.get('market_reaction', ''))}<br>"
                f"반대 근거: {html.escape(item.get('counter_evidence', ''))}<br>"
                f"다음 확인: {html.escape(item.get('what_to_watch', ''))}<br>"
                f"출처: {' · '.join(source_links) if source_links else '출처 링크 없음'}</li>"
            )
        html_sections.append("<h2>Top Story Clusters</h2><ol>" + "".join(story_html) + "</ol>")
    else:
        html_sections.append("<h2>Top Story Clusters</h2><ul>" + ("".join(f"<li>{html.escape(item)}</li>" for item in news) if news else "<li>추가 관련 뉴스 없음</li>") + "</ul>")
    html_sections.extend([
        "<h2>오늘 경제 캘린더 — KST</h2><ul>" + ("".join(f"<li>{html.escape(item)}</li>" for item in econ) if econ else "<li>경제 캘린더 데이터 없음 또는 소스 오류</li>") + "</ul>",
        "<h2>오늘 주요 실적</h2><ul>" + ("".join(f"<li>{html.escape(item)}</li>" for item in earnings) if earnings else "<li>주요 실적 데이터 없음</li>") + "</ul>",
    ])
    if options:
        html_sections.append("<h2>옵션 / OI</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in options) + "</ul>")
    if insight.get("what_to_watch"):
        html_sections.append("<h2>오늘 확인할 것</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in insight["what_to_watch"][:5]) + "</ul>")
    if insight.get("research_needed"):
        html_sections.append("<p><small>큰 움직임의 원인에 대한 외부 심층 확인은 조사 대기 중이며, 인과는 확정하지 않았습니다.</small></p>")
    quality_html = "<h2><small>데이터 품질</small></h2><ul>" + "".join(f"<li><small>{html.escape(str(item))}</small></li>" for item in quality) + "</ul>" if quality else ""
    html_body = "<html><body style=\"font-family:Arial,sans-serif;line-height:1.55\">" + "".join(html_sections) + "<p><small>동일 canonical snapshot 기반. 원인 해석은 확인 가능한 근거와 함께 구분합니다.</small></p>" + quality_html + "</body></html>"
    return subject, plain, html_body
