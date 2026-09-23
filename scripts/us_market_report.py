#!/usr/bin/env python3
"""Legacy US market report backed by the R1 shared data core.

Legacy top-level keys remain stable. Yahoo regular-session OHLC is the price
authority; CBOE is limited to IV/open-interest fields.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timedelta, timezone

from market_board import collect_market_board
from market_clock import KST, get_market_clock
from market_data import RunCache, cboe_chain_summary, fetch_url, yahoo_chart_quote
from report_snapshots import persist_report_snapshot
from state_store import load_oi_baseline


def fetch(url, timeout=15):
    return fetch_url(url, timeout)


def yahoo_quote(symbol, cache=None):
    return yahoo_chart_quote(symbol, cache=cache, fetcher=fetch)


def _parse_rfc1123(value: str) -> str:
    try:
        parsed = datetime.strptime(value.replace("GMT", "+0000").replace("UTC", "+0000"), "%a, %d %b %Y %H:%M:%S %z")
        return parsed.astimezone(KST).strftime("%m-%d %H:%M")
    except Exception:
        return value


def collect_earnings(session_date):
    try:
        document = json.loads(fetch(f"https://api.nasdaq.com/api/calendar/earnings?date={session_date.isoformat()}"))
        rows = document.get("data", {}).get("rows", []) or []
        return [{
            "symbol": row.get("symbol"), "name": row.get("name"),
            "time": (row.get("time") or "").replace("time-", ""),
            "eps_forecast": row.get("epsForecast"), "market_cap": row.get("marketCap"),
            "target_session_date": session_date.isoformat(),
        } for row in rows[:15]]
    except Exception as error:
        return [{"error": str(error)[:80], "target_session_date": session_date.isoformat()}]


def collect_news():
    news = []
    try:
        xml = fetch("https://www.cnbc.com/id/100003114/device/rss/rss.html").decode("utf-8", "replace")
        for item in re.findall(r"<item>(.*?)</item>", xml, re.S)[:12]:
            def grab(tag):
                match = re.search(rf"<{tag}>(.*?)</{tag}>", item, re.S)
                return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip() if match else ""
            title, link, desc, published = grab("title"), grab("link"), grab("description"), grab("pubDate")
            if title:
                news.append({"title": title, "link": link, "desc": desc[:220], "time": _parse_rfc1123(published)})
    except Exception as error:
        news.append({"error": str(error)[:80]})
    return news


def collect_econ():
    events = []
    try:
        html_text = fetch("https://www.investing.com/economic-calendar/", timeout=20).decode("utf-8", "replace")
        now = datetime.now(timezone.utc)
        for raw in re.findall(r'\{[^{}]*?"event"[^{}]*?\}', html_text):
            try:
                event = json.loads(raw)
                if event.get("currency") != "USD" or int(event.get("importance") or 0) < 2:
                    continue
                timestamp = event.get("time")
                if not timestamp:
                    continue
                when = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if when < now - timedelta(hours=6) or when > now + timedelta(days=2):
                    continue
                events.append({
                    "time": when.astimezone(KST).strftime("%m-%d %H:%M"),
                    "event": event.get("event", ""), "importance": int(event.get("importance") or 0),
                    "actual": event.get("actual", ""), "forecast": event.get("forecast", ""),
                    "previous": event.get("previous", ""),
                })
            except Exception:
                continue
        return sorted(events, key=lambda item: item["time"])[:15]
    except Exception as error:
        return [{"error": str(error)[:80]}]


def _cboe_option_data(symbol, yahoo, cache):
    option = cboe_chain_summary(symbol, cache=cache, fetcher=fetch, sleep_seconds=0, reference_price=yahoo.get("price"))
    return {
        "price": yahoo.get("price"),
        "change_pct": yahoo.get("change_pct"),
        "price_source": yahoo.get("source", "yahoo_regular_ohlc"),
        "iv30": option.get("iv30"),
        "call_oi": option.get("call_oi"),
        "put_oi": option.get("put_oi"),
        "total_oi": option.get("total_oi"),
        "oi_change": None,
        "oi_top": option.get("oi_top", []),
        "atm": option.get("atm"),
        "1sd_30d": round((yahoo.get("price") or 0) * (option.get("sd_pct") or 0) / 100, 2) if option.get("sd_pct") else None,
        "source": "cboe_options",
        "reference_window": "options_chain",
    }


def main(phase=None):
    clock = get_market_clock(phase)
    cache = RunCache()
    spot = ["^GSPC", "^IXIC", "^NDX", "^DJI", "^RUT", "SOXX"]
    futures = ["ES=F", "NQ=F", "YM=F", "RTY=F"]
    extra = ["CL=F", "DX-Y.NYB", "^TNX", "^TYX", "KRW=X", "^VIX", "GC=F", "SI=F"]
    quotes = {}
    for symbol in spot + futures + extra:
        try:
            quotes[symbol] = yahoo_quote(symbol, cache)
        except Exception as error:
            quotes[symbol] = {"symbol": symbol, "error": str(error)[:80], "source": "unavailable"}

    output = {
        "generated_at": clock.now_kst.strftime("%Y-%m-%d %H:%M%z"),
        "meta": clock.as_dict(),
        "quotes": quotes,
        "trending": [],
        "earnings": collect_earnings(clock.market_session_date),
        "news": collect_news(),
        "econ_calendar": collect_econ(),
    }
    try:
        trending_doc = json.loads(fetch("https://query1.finance.yahoo.com/v1/finance/trending/US"))
        symbols = [item["symbol"] for item in trending_doc["finance"]["result"][0]["quotes"]][:8]
        for symbol in symbols:
            try:
                output["trending"].append(yahoo_quote(symbol, cache))
            except Exception as error:
                output["trending"].append({"symbol": symbol, "error": str(error)[:80]})
    except Exception as error:
        output["trending_error"] = str(error)[:80]

    output["indicators"] = collect_market_board(cache)["indicators"]

    option_symbols = ["NVDA", "SNDK", "MU", "SKHY", "AMD", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "SPCX"]
    output["options"] = {}
    baseline = load_oi_baseline(clock.market_session_date)["snapshots"]
    for symbol in option_symbols:
        try:
            quote = yahoo_quote(symbol, cache)
            option_data = _cboe_option_data(symbol, quote, cache)
            prior = baseline.get(symbol, {})
            if prior.get("total_oi") is not None and option_data.get("total_oi") is not None:
                option_data["oi_change"] = option_data["total_oi"] - prior["total_oi"]
            output["options"][symbol] = option_data
        except Exception as error:
            output["options"][symbol] = {"error": str(error)[:80]}
    output["oi_top5"] = [symbol for _, symbol in sorted(
        ((value.get("total_oi") or 0, symbol) for symbol, value in output["options"].items() if "error" not in value),
        reverse=True,
    )[:5]]

    snapshot = persist_report_snapshot(clock.phase, output, clock.market_session_date)
    print(json.dumps(snapshot, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("morning", "evening", "open", "close"))
    main(parser.parse_args().phase)
