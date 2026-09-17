#!/usr/bin/env python3
"""미국 증시 보고 데이터 수집 — 아침 7시/저녁 9시 크론잡용.

수집: 지수/선물 시세(Yahoo, 캔들 기반 등락), 화제 종목+기업명+등락(Yahoo),
실적 발표(Nasdaq), 뉴스+시간(CNBC RSS), 경제 캘린더(investing.com).
stdout으로 JSON 출력 → 크론잡 LLM이 한국어 보고서로 가공.
"""
import json
import os
import re
import html
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def get_env(key):
    """%LOCALAPPDATA%/hermes/.env 에서 키 값 읽기."""
    try:
        env_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", ".env")
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None

def twelve_quote(symbol):
    """Twelve Data 폴백 — 종목/ETF 시세 (지수·선물·FX는 무료 티어 불가)."""
    key = get_env("TWELVEDATA_API_KEY")
    if not key:
        raise Exception("TWELVEDATA_API_KEY 없음")
    url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={key}"
    d = json.loads(fetch(url))
    if "code" in d or "message" in d:
        raise Exception(str(d.get("message", "twelve error"))[:60])
    price = float(d.get("close") or 0)
    prev = float(d.get("previous_close") or 0)
    chg = round(price - prev, 2) if prev else None
    pct = round((price - prev) / prev * 100, 2) if prev else None
    return {
        "symbol": symbol,
        "name": d.get("name") or symbol,
        "price": price,
        "prev": prev,
        "change": chg,
        "change_pct": pct,
        "data_date": (d.get("datetime") or "")[:10],
        "fallback": "twelve",
    }

def yahoo_quote(symbol):
    """Yahoo chart API — 캔들 마지막 2개로 전일 대비 등락 계산."""
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol)
        + "?range=5d&interval=1d"
    )
    d = json.loads(fetch(url))
    res = d["chart"]["result"][0]
    m = res["meta"]
    ts = res.get("timestamp", [])
    closes = res["indicators"]["quote"][0].get("close", [])
    price = m.get("regularMarketPrice")
    prev = None
    data_date = None
    if len(closes) >= 2:
        # 마지막 2개 유효 캔들
        valid = [(t, c) for t, c in zip(ts, closes) if c is not None]
        if len(valid) >= 2:
            prev = valid[-2][1]
            data_date = datetime.fromtimestamp(valid[-1][0], tz=timezone.utc).strftime("%m-%d")
    chg = round(price - prev, 2) if (prev and price) else None
    pct = round((price - prev) / prev * 100, 2) if (prev and price) else None
    return {
        "symbol": symbol,
        "name": m.get("shortName") or m.get("longName") or symbol,
        "price": price,
        "prev": prev,
        "change": chg,
        "change_pct": pct,
        "data_date": data_date,
    }

def main():
    out = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M")}

    # 1) 시세: 현물 6종 + 선물 4종 + 원유/달러/금리/환율/VIX/금은 (캔들 기반 등락)
    SPOT = ["^GSPC", "^IXIC", "^NDX", "^DJI", "^RUT", "SOXX"]
    FUT = ["ES=F", "NQ=F", "YM=F", "RTY=F"]
    EXTRA = ["CL=F", "DX-Y.NYB", "^TNX", "^TYX", "KRW=X", "^VIX", "GC=F", "SI=F"]  # 원유/달러/금리/환율/VIX/금선물/은선물
    quotes = {}
    for s in SPOT + FUT + EXTRA:
        try:
            quotes[s] = yahoo_quote(s)
        except Exception as e:
            # Twelve Data 폴백 (순수 종목/ETF만 — 지수 ^, 선물 =F, FX =X는 무료 티어 불가)
            if not s.startswith("^") and not s.endswith("=F") and not s.endswith("=X"):
                try:
                    quotes[s] = twelve_quote(s)
                except Exception as e2:
                    quotes[s] = {"symbol": s, "error": str(e)[:80]}
            else:
                quotes[s] = {"symbol": s, "error": str(e)[:80]}
    out["quotes"] = quotes

    # 2) 화제 종목 + 기업명 + 등락 (Yahoo Trending → 각 종목 시세)
    trending = []
    try:
        d = json.loads(fetch("https://query1.finance.yahoo.com/v1/finance/trending/US"))
        syms = [q["symbol"] for q in d["finance"]["result"][0]["quotes"]][:8]
        for s in syms:
            try:
                q = yahoo_quote(s)
                trending.append(q)
            except Exception:
                trending.append({"symbol": s, "name": "", "error": "시세 조회 실패"})
    except Exception as e:
        out["trending_error"] = str(e)[:80]
    out["trending"] = trending

    # 3) 오늘 실적 발표 (Nasdaq 공식 API)
    try:
        today = date.today().isoformat()
        d = json.loads(
            fetch(f"https://api.nasdaq.com/api/calendar/earnings?date={today}")
        )
        rows = d.get("data", {}).get("rows", []) or []
        out["earnings"] = [
            {
                "symbol": r.get("symbol"),
                "name": r.get("name"),
                "time": (r.get("time") or "").replace("time-", ""),
                "eps_forecast": r.get("epsForecast"),
                "market_cap": r.get("marketCap"),
            }
            for r in rows[:15]
        ]
    except Exception as e:
        out["earnings"] = []
        out["earnings_error"] = str(e)[:80]

    # 4) CNBC 주요 뉴스 (제목/링크/시간)
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
            # pubDate → KST 표기
            pub_kst = ""
            if pub:
                try:
                    # "Thu, 06 Aug 2026 12:17:28 GMT" → RFC1123 + GMT
                    pub2 = pub.replace("GMT", "+0000").replace("UTC", "+0000")
                    dt = datetime.strptime(pub2, "%a, %d %b %Y %H:%M:%S %z")
                    pub_kst = (dt.astimezone(timezone(timedelta(hours=9)))).strftime("%m-%d %H:%M")
                except Exception:
                    pub_kst = pub
            if title:
                news.append({"title": title, "link": link, "desc": desc[:220], "time": pub_kst})
    except Exception as e:
        news.append({"error": str(e)[:80]})
    out["news"] = news

    # 5) 경제 캘린더 (investing.com — USD 이벤트, 중요도 2+, 오늘~내일)
    econ = []
    try:
        htm = fetch("https://www.investing.com/economic-calendar/", timeout=20).decode("utf-8", "replace")
        objs = re.findall(r'\{[^{}]*?"event"[^{}]*?\}', htm)
        now = datetime.now(timezone.utc)
        for o in objs:
            try:
                ev = json.loads(o)
                if ev.get("currency") != "USD":
                    continue
                imp = int(ev.get("importance") or 0)
                if imp < 2:
                    continue
                t = ev.get("time", "")
                if not t:
                    continue
                et = datetime.fromisoformat(t.replace("Z", "+00:00"))
                if et < now - timedelta(hours=6) or et > now + timedelta(days=2):
                    continue
                econ.append({
                    "time": et.astimezone(timezone(timedelta(hours=9))).strftime("%m-%d %H:%M"),
                    "event": ev.get("event", ""),
                    "importance": imp,
                    "actual": ev.get("actual", ""),
                    "forecast": ev.get("forecast", ""),
                    "previous": ev.get("previous", ""),
                })
            except Exception:
                continue
        econ.sort(key=lambda x: x["time"])
        out["econ_calendar"] = econ[:15]
    except Exception as e:
        out["econ_calendar"] = []
        out["econ_error"] = str(e)[:80]

    # 6) 옵션 섹션 (CBOE 지연 API — 개별 종목 옵션 체인)
    #    추적 종목(12) + 화제 종목(Trending 상위 8) 중복 제거 → 최대 20종 조회
    #    SpaceX(SPCX)는 상장됨 — 옵션 존재 확인 완료. SK하이닉스 ADR = SKHY.
    OPTIONS = ["NVDA", "SNDK", "MU", "SKHY", "AMD", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "SPCX"]
    try:
        d2 = json.loads(fetch("https://query1.finance.yahoo.com/v1/finance/trending/US"))
        for q in d2["finance"]["result"][0]["quotes"]:
            sym = q["symbol"]
            if len(OPTIONS) >= 20:
                break
            if sym not in OPTIONS and not sym.endswith("-USD"):
                OPTIONS.append(sym)
    except Exception:
        pass

    # 전일 OI 스냅샷 로드 (OI 변동 계산용)
    snap_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oi_snapshot.json")
    prev_snap = {}
    try:
        with open(snap_path, encoding="utf-8") as f:
            prev_snap = json.load(f)
    except Exception:
        prev_snap = {}

    option_data = {}
    for s in OPTIONS:
        try:
            d = json.loads(fetch(f"https://cdn.cboe.com/api/global/delayed_quotes/options/{s}.json", timeout=20))
            data = d["data"]
            opts = data.get("options") or []
            cp = data.get("current_price")
            # OI TOP3 (계약명 마지막 8자리=strike, 9번째=C/P)
            oi_sorted = sorted(opts, key=lambda o: o.get("open_interest") or 0, reverse=True)[:3]
            oi_top = []
            for o in oi_sorted:
                try:
                    strike = int(o["option"][-8:]) / 1000
                    ctype = o["option"][-9]
                    oi_top.append({"strike": strike, "type": ctype, "oi": o.get("open_interest"), "iv": round(o.get("iv") or 0, 4)})
                except Exception:
                    continue
            # ATM 옵션 (현재가와 가장 가까운 strike)
            atm = None
            if cp and opts:
                try:
                    atm_o = min(opts, key=lambda o: abs((int(o["option"][-8:]) / 1000) - cp))
                    atm = {"strike": int(atm_o["option"][-8:]) / 1000, "type": atm_o["option"][-9],
                           "iv": round(atm_o.get("iv") or 0, 4), "oi": atm_o.get("open_interest")}
                except Exception:
                    pass
            # 총 OI (전체 계약 합) + 전일 대비 변동
            total_oi = sum(o.get("open_interest") or 0 for o in opts)
            prev_total = prev_snap.get(s, {}).get("total_oi")
            oi_change = (total_oi - prev_total) if prev_total is not None else None
            # 1시그마(30일): 1SD = price × iv30 × sqrt(30/365)
            # (CBOE iv30은 백분율 포인트 값 — 예: 42.686 = 42.7% → 소수로 변환)
            iv30_dec = None
            if data.get("iv30") is not None:
                iv30_raw = data.get("iv30")
                iv30_dec = iv30_raw / 100 if iv30_raw > 1 else iv30_raw
            sd30 = None
            if cp and iv30_dec:
                sd30 = round(cp * iv30_dec * (30 / 365) ** 0.5, 2)
            option_data[s] = {
                "price": cp,
                "change_pct": data.get("price_change_percent"),
                "iv30": iv30_dec,
                "total_oi": total_oi,
                "oi_change": oi_change,
                "oi_top": oi_top,
                "atm": atm,
                "1sd_30d": sd30,
            }
        except Exception as e:
            option_data[s] = {"error": str(e)[:60]}
    out["options"] = option_data

    # OI TOP5 (조회한 전체 종목 중 금일 총 OI 기준)
    ranked = sorted(
        [(v.get("total_oi") or 0, s) for s, v in option_data.items() if "error" not in v],
        reverse=True,
    )
    out["oi_top5"] = [s for _, s in ranked[:5]]

    # 전일 OI 스냅샷 갱신 (다음 실행의 전일 대비 비교용)
    try:
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump({s: {"total_oi": v.get("total_oi")} for s, v in option_data.items() if "error" not in v}, f, ensure_ascii=False)
    except Exception:
        pass

    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()
