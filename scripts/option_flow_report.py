#!/usr/bin/env python3
"""옵션플로우 브리핑 수집 — 미국 장 시작(open)/종료(close) 크론잡용.

open  : 전일 마감 신호(prev_signals) + 선물 방향 + 오늘 실적/경제/뉴스 → 프리마켓 브리핑
close : 61종 옵션 콜/풋 OI 증감 감지 + 자체 컨빅션 스코어 + 1σ 이탈 + 시장 백드롭
        + 전일 신호 결과 검증(종가/고점/저점) → 장 마감 종합 브리핑
        (샘플 형식: 백드롭 → 🟢/🔴 신호 → 결과 → 비정상 OI 감지)

모든 소스 무료(실측 검증): CBOE 지연 옵션 API, Yahoo chart, Nasdaq 실적,
CNBC RSS, investing.com 경제 캘린더. stdout JSON → 크론 LLM이 한국어 브리핑 가공.

용법: python option_flow_report.py open|close
"""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import time

from market_clock import ET, KST, get_market_clock
from market_data import RunCache, cboe_chain_summary, fetch_url, yahoo_chart_quote, yahoo_daily_last as shared_yahoo_daily_last
from report_snapshots import persist_report_snapshot
from state_store import atomic_write_json, commit_oi_close, load_flow_signals, load_oi_baseline, read_json, state_path

_RUN_CACHE = RunCache()

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
# 고정 유니버스 56종 (+ Trending 상위 5 = 61종)
UNIVERSE = [
    # 기존 추적 12
    "NVDA", "SNDK", "MU", "SKHY", "AMD", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "SPCX",
    # 반도체 13
    "AVGO", "TSM", "INTC", "QCOM", "ARM", "ASML", "LRCX", "AMAT", "KLAC", "MRVL", "SMCI", "IREN", "NBIS",
    # 소프트웨어/인터넷 13
    "CRM", "ORCL", "NFLX", "ADBE", "PYPL", "SHOP", "PLTR", "SNOW", "DDOG", "NET", "TEAM", "DOCS", "U",
    # 금융/핀테크 8
    "COIN", "HOOD", "SOFI", "JPM", "BAC", "C", "GS", "MS",
    # 대형 10
    "DIS", "KO", "PEP", "WMT", "XOM", "CVX", "BA", "CAT", "UNH", "JNJ",
]

SPOT = ["^GSPC", "^IXIC", "^NDX", "^DJI", "^RUT", "SOXX"]
FUT = ["ES=F", "NQ=F", "YM=F", "RTY=F"]
EXTRA = ["CL=F", "DX-Y.NYB", "^TNX", "^TYX", "KRW=X", "^VIX", "GC=F", "SI=F"]


def fetch(url, timeout=20):
    return fetch_url(url, timeout)


def yahoo_quote(symbol):
    return yahoo_chart_quote(symbol, cache=_RUN_CACHE, fetcher=fetch)


def yahoo_daily_last(symbol):
    return shared_yahoo_daily_last(symbol, cache=_RUN_CACHE, fetcher=fetch)


def fetch_cboe(sym):
    """CBOE 지연 옵션 — 콜/풋 총 OI, iv30(소수), 1SD%. 계약명 9번째 문자 = C/P.

    ⚠️ 실측(2026-08): 병렬 61연발은 429 유발 → 반드시 순차 호출 + 429 시 10/30/60초 백오프.
    ⚠️ CBOE current_price/price_change_percent는 **애프터/프리마켓 가격을 반영**함
        (실적발표 급등분이 종가에 포함됨 — TEAM +30.4% 오류 실측).
        → 가격·등락은 반드시 Yahoo 정규장(yahoo_quote)을 정본으로 사용. 여기선 OI/IV만.
    """
    return cboe_chain_summary(sym, cache=_RUN_CACHE, fetcher=fetch)


def conv_score(chg_pct, price_chg_pct, iv30, sigma_hit):
    """자체 컨빅션 스코어(0~100): OI 변동 35 + 주가 움직임 30 + IV 레벨 20 + 1σ 보너스 15."""
    s = min(abs(chg_pct or 0) / 50, 1) * 35 + min(abs(price_chg_pct or 0) / 5, 1) * 30
    if iv30:
        s += min(iv30 / 1.0, 1) * 20
    if sigma_hit:
        s += 15
    return round(s)


def verdict(direction, close_pct):
    if close_pct is None:
        return "데이터없음"
    if abs(close_pct) < 0.5:
        return "flat(보합)"
    if (direction == "bullish" and close_pct > 0) or (direction == "bearish" and close_pct < 0):
        return "hit(적중)"
    return "miss(빗나감)"


def backdrop(quotes):
    """시장 백드롭: 지수 4종 + SOXX + VIX 조합 → -100~+100."""
    def pct(s):
        q = quotes.get(s, {})
        return q.get("change_pct") or 0
    score = round(
        pct("^GSPC") * 12 + pct("^IXIC") * 10 + pct("^DJI") * 8 + pct("^RUT") * 10
        + pct("SOXX") * 4 - (quotes.get("^VIX", {}).get("change") or 0) * 3
    )
    if score <= -60:
        label = "strong_bearish(약세 가속)"
    elif score <= -45:
        label = "bearish(약세)"
    elif score <= -20:
        label = "slight_bearish(약한 약세)"
    elif score < 20:
        label = "neutral(혼조)"
    elif score < 45:
        label = "slight_bullish(약한 상승)"
    elif score < 60:
        label = "bullish(상승)"
    else:
        label = "strong_bullish(상승 가속)"
    return {"score": score, "label": label}


def load_json(path):
    return read_json(path)


def save_json(path, obj):
    atomic_write_json(path, obj)


def collect_earnings(session_date):
    try:
        d = json.loads(fetch(f"https://api.nasdaq.com/api/calendar/earnings?date={session_date.isoformat()}"))
        rows = d.get("data", {}).get("rows", []) or []
        return [
            {"symbol": r.get("symbol"), "name": r.get("name"),
             "time": (r.get("time") or "").replace("time-", ""),
             "eps_forecast": r.get("epsForecast"), "market_cap": r.get("marketCap")}
            for r in rows[:15]
        ]
    except Exception as e:
        return [{"error": str(e)[:60]}]


def collect_news():
    news = []
    try:
        xml = fetch("https://www.cnbc.com/id/100003114/device/rss/rss.html").decode("utf-8", "replace")
        items = re.findall(r"<item>(.*?)</item>", xml, re.S)
        for it in items[:12]:
            def grab(tag):
                m = re.search(rf"<{tag}>(.*?)</{tag}>", it, re.S)
                if not m:
                    return ""
                return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
            title, link, desc = grab("title"), grab("link"), grab("description")
            pub = grab("pubDate")
            pub_kst = ""
            if pub:
                try:
                    pub2 = pub.replace("GMT", "+0000").replace("UTC", "+0000")
                    dt = datetime.strptime(pub2, "%a, %d %b %Y %H:%M:%S %z")
                    pub_kst = dt.astimezone(KST).strftime("%m-%d %H:%M")
                except Exception:
                    pub_kst = pub
            if title:
                news.append({"title": title, "link": link, "desc": desc[:220], "time": pub_kst})
    except Exception as e:
        news.append({"error": str(e)[:60]})
    return news


def collect_econ():
    econ = []
    try:
        htm = fetch("https://www.investing.com/economic-calendar/", timeout=25).decode("utf-8", "replace")
        objs = re.findall(r'\{[^{}]*?"event"[^{}]*?\}', htm)
        now = datetime.now(timezone.utc)
        for o in objs:
            try:
                ev = json.loads(o)
                if ev.get("currency") != "USD" or int(ev.get("importance") or 0) < 2:
                    continue
                t = ev.get("time", "")
                if not t:
                    continue
                et = datetime.fromisoformat(t.replace("Z", "+00:00"))
                if et < now - timedelta(hours=6) or et > now + timedelta(days=2):
                    continue
                econ.append({
                    "time": et.astimezone(KST).strftime("%m-%d %H:%M"),
                    "event": ev.get("event", ""), "importance": ev.get("importance"),
                    "actual": ev.get("actual", ""), "forecast": ev.get("forecast", ""),
                    "previous": ev.get("previous", ""),
                })
            except Exception:
                continue
        econ.sort(key=lambda x: x["time"])
        return econ[:15]
    except Exception as e:
        return [{"error": str(e)[:60]}]


def main(mode):
    if mode not in ("open", "close"):
        print(json.dumps({"error": "mode must be open|close"}, ensure_ascii=False))
        return 1
    global _RUN_CACHE
    _RUN_CACHE = RunCache()
    clock = get_market_clock(mode)

    out = {"generated_at": clock.now_kst.strftime("%Y-%m-%d %H:%M%z"), "mode": mode, "meta": clock.as_dict()}

    # 1) 시세 18종 + 세션 라벨
    quotes = {}
    for s in SPOT + FUT + EXTRA:
        try:
            quotes[s] = yahoo_quote(s)
        except Exception as e:
            quotes[s] = {"symbol": s, "error": str(e)[:60]}
    out["quotes"] = quotes
    ses = quotes.get("^GSPC", {}).get("et_date") or ""
    out["session_label"] = (f"미국장 {ses} 마감 신호 → 오늘 장 전망" if mode == "open"
                            else f"미국장 {ses} 마감 기준") if ses else ""
    out["market_backdrop"] = backdrop(quotes)

    # 2) 유니버스: 고정 56 + Trending 5 = 61
    universe = list(UNIVERSE)
    try:
        d = json.loads(fetch("https://query1.finance.yahoo.com/v1/finance/trending/US"))
        for q in d["finance"]["result"][0]["quotes"]:
            sym = q["symbol"]
            if len(universe) >= 61:
                break
            if sym not in universe and not sym.endswith("-USD"):
                universe.append(sym)
    except Exception:
        pass
    out["universe_size"] = len(universe)

    if mode == "open":
        # 3) 전일 마감 신호 재표시 (오늘 관전 포인트)
        prev = load_flow_signals()
        out["prev_signals"] = prev.get("signals", [])
        out["prev_session"] = prev.get("date", "")
    else:
        # 3) CBOE 61종 순차 수집 (⚠️ 병렬 61연발은 429 유발 — 실측. 반드시 순차)
        #    가격·등락은 CBOE가 아니라 Yahoo 정규장(yahoo_quote)을 정본으로 사용
        #    CBOE current quote fields are ignored because they can include after-hours data.
        option_data = {}
        for s in universe:
            try:
                o = fetch_cboe(s)
                # Yahoo 정규장 가격/등락 병합
                try:
                    q = yahoo_quote(s)
                    o["price"] = q.get("price")
                    o["price_chg_pct"] = q.get("change_pct")
                    o["price_error"] = q.get("error")
                except Exception as e:
                    o["price"] = None
                    o["price_chg_pct"] = None
                    o["price_error"] = str(e)[:60]
                option_data[s] = o
            except Exception as e:
                option_data[s] = {"error": str(e)[:60]}

        # 4) 전일 스냅샷 대비 OI 증감 → 비정상 OI + 컨빅션 신호
        prev_snap = load_oi_baseline(clock.market_session_date)["snapshots"]
        signals, anomalies = [], []
        for s, o in option_data.items():
            if "error" in o or not o.get("total_oi"):
                continue
            p = prev_snap.get(s, {})
            call_chg = None
            put_chg = None
            if p.get("call_oi"):
                call_chg = round((o["call_oi"] - p["call_oi"]) / p["call_oi"] * 100, 1)
            if p.get("put_oi"):
                put_chg = round((o["put_oi"] - p["put_oi"]) / p["put_oi"] * 100, 1)
            price_chg = o.get("price_chg_pct")
            sigma_hit = bool(price_chg is not None and o.get("sd_pct") and abs(price_chg) > o["sd_pct"])
            # 비정상 OI: 🔴풋 = 풋 OI +10% & 주가 -1% 이하 / 🟢콜 = 콜 OI +10% & 주가 +1% 이상
            for side, chg in (("put", put_chg), ("call", call_chg)):
                if chg is None or chg < 10 or price_chg is None:
                    continue
                if side == "put" and price_chg <= -1:
                    anomalies.append({"ticker": s, "side": "put", "direction": "bearish",
                                      "oi_chg_pct": chg, "price_chg_pct": price_chg})
                elif side == "call" and price_chg >= 1:
                    anomalies.append({"ticker": s, "side": "call", "direction": "bullish",
                                      "oi_chg_pct": chg, "price_chg_pct": price_chg})
            # 컨빅션 신호 (방향별 OI 급증 + 주가 방향 일치)
            cand = None
            if call_chg is not None and call_chg >= 10 and price_chg is not None and price_chg >= 1:
                cand = ("bullish", "call", call_chg)
            elif put_chg is not None and put_chg >= 10 and price_chg is not None and price_chg <= -1:
                cand = ("bearish", "put", put_chg)
            if cand:
                direction, side, chg = cand
                signals.append({
                    "ticker": s, "direction": direction, "side": side,
                    "score": conv_score(chg, price_chg, o.get("iv30"), sigma_hit),
                    "call_oi_chg_pct": call_chg, "put_oi_chg_pct": put_chg,
                    "price_chg_pct": price_chg, "iv30": o.get("iv30"),
                    "sd_pct": o.get("sd_pct"), "sigma_breakout": sigma_hit,
                    "signal_price": o.get("price"),
                })
        signals.sort(key=lambda x: x["score"], reverse=True)
        top_bull = [s for s in signals if s["direction"] == "bullish"][:4]
        top_bear = [s for s in signals if s["direction"] == "bearish"][:4]
        out["signals"] = top_bull + top_bear
        # Preserve the close option map in latest_close.json for the morning
        # delivery renderer; the dedicated OI snapshot remains the baseline authority.
        out["options"] = option_data
        anomalies.sort(key=lambda x: x["oi_chg_pct"], reverse=True)
        out["oi_anomalies"] = anomalies

        # 5) 전일 신호 결과 검증 (종가/고점/저점 %)
        prev = load_flow_signals()
        verification = []
        if prev.get("signals"):
            def verify_one(sig):
                try:
                    ohlc = yahoo_daily_last(sig["ticker"])
                    if not ohlc or not sig.get("signal_price"):
                        return None
                    ref = sig["signal_price"]
                    return {
                        "ticker": sig["ticker"], "direction": sig["direction"],
                        "score": sig.get("score"),
                        "signal_price": ref, "session": ohlc["date"],
                        "close_pct": round((ohlc["close"] / ref - 1) * 100, 2),
                        "high_pct": round((ohlc["high"] / ref - 1) * 100, 2),
                        "low_pct": round((ohlc["low"] / ref - 1) * 100, 2),
                        "verdict": verdict(sig["direction"], round((ohlc["close"] / ref - 1) * 100, 2)),
                    }
                except Exception:
                    return None
            with ThreadPoolExecutor(max_workers=6) as ex:
                futs = {ex.submit(verify_one, s): s for s in prev["signals"]}
                for f in as_completed(futs):
                    r = f.result()
                    if r:
                        verification.append(r)
        out["verification"] = verification

        # 6) 스냅샷·신호 저장 (다음 실행의 전일 대비 기준)
        commit_oi_close(clock.market_session_date, {
            s: {"call_oi": o.get("call_oi"), "put_oi": o.get("put_oi"), "total_oi": o.get("total_oi")}
            for s, o in option_data.items() if "error" not in o and o.get("total_oi")
        }, owner="option_flow_close")
        save_json(state_path("option", "flow_signals.json"), {
            "schema_version": 1, "generated_at": clock.now_kst.isoformat(),
            "session_date": clock.market_session_date.isoformat(), "date": ses, "signals": out["signals"],
        })

    # 7) 공통: 실적/뉴스/경제 캘린더 (open 모드는 전망용으로 핵심)
    out["earnings"] = collect_earnings(clock.market_session_date)
    out["news"] = collect_news()
    out["econ_calendar"] = collect_econ() if mode == "open" else []

    print(json.dumps(persist_report_snapshot(mode, out, clock.market_session_date), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "close"))
