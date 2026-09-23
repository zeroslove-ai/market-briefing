"""Compose deterministic Insight Engine R1 output from one canonical payload."""

from __future__ import annotations

from insight_claims import build_claims
from insight_features import calculate_features, detect_anomalies
from insight_news import build_research_queue, rank_and_cluster_news, write_research_queue


CLAIM_TEXT = {
    "SEMI_LEADERSHIP": "반도체가 S&P를 크게 앞서 성장주 강세를 주도했습니다.",
    "SMALL_CAP_LAG": "Russell이 Nasdaq보다 뒤처져 강세가 소형주까지 넓게 확산되지는 않았습니다.",
    "NARROW_GROWTH_RISK_ON": "성장주 중심의 선택적 위험선호입니다. 시장 전체의 동반 강세로 보기는 이릅니다.",
    "BROAD_RISK_ON": "주식과 여러 교차자산 지표가 함께 개선돼 위험선호가 비교적 넓게 확인됩니다.",
    "RISK_OFF_CONFIRMED": "주식 약세에 변동성·금리 상승이 동반돼 방어 신호가 겹쳤습니다.",
    "CROSS_ASSET_MIXED": "주식과 일부 교차자산 신호가 엇갈려 일방적인 위험선호 확인은 부족합니다.",
    "RATES_TAILWIND_GROWTH": "10년 금리 하락은 성장주의 할인율 부담을 낮추는 방향과 맞물렸습니다.",
    "RATES_HEADWIND_GROWTH": "10년 금리 상승과 성장주 약세가 겹쳐 할인율 부담을 확인할 필요가 있습니다.",
    "VOLATILITY_EXPANSION": "VIX가 크게 올라 옵션시장이 반영하는 단기 변동성 부담이 확대됐습니다.",
    "OIL_DISINFLATION_TAILWIND": "유가 하락은 물가 부담 완화와 양립하지만 공급·수요 원인은 별도 확인이 필요합니다.",
    "OIL_DEMAND_SCARE": "유가와 주식이 함께 약해 수요 우려 가능성을 살펴야 하지만 원인으로 단정할 수 없습니다.",
    "CRYPTO_CONFIRMATION": "BTC 상승이 위험자산 선호를 보조 확인하지만 주식과 비교 기간은 다릅니다.",
    "FUTURES_DIVERGENCE": "선물 방향이 직전 현물과 달라 개장 전 위험선호가 약해졌는지 확인이 필요합니다.",
    "SIGMA_OI_CONFIRMED": "Sigma 구간과 OI 이상 신호가 함께 관찰됩니다. 포지션 의도를 뜻하지는 않습니다.",
    "SIGMA_OI_CONFLICT": "Sigma 상태와 뚜렷한 OI 확인이 일치하지 않아 가격 반응을 더 봐야 합니다.",
}
CLAIM_PRIORITY = (
    "NARROW_GROWTH_RISK_ON", "RATES_TAILWIND_GROWTH", "OIL_DISINFLATION_TAILWIND",
    "OIL_DEMAND_SCARE", "CROSS_ASSET_MIXED", "SEMI_LEADERSHIP", "SMALL_CAP_LAG",
    "RISK_OFF_CONFIRMED", "BROAD_RISK_ON", "RATES_HEADWIND_GROWTH",
    "VOLATILITY_EXPANSION", "CRYPTO_CONFIRMATION", "FUTURES_DIVERGENCE",
)


def _market_map(features: dict) -> list[dict]:
    rows = []
    definitions = [
        ("S&P 500", "sp500", "sp500"), ("Nasdaq", "nasdaq_composite", "nasdaq"),
        ("Russell 2000", "russell_2000", "russell"), ("SOXX", "soxx", "soxx"),
        ("10년물", "us10y_change_bp", "rates"), ("30년물", "us30y_change_bp", "rates"),
        ("VIX", "vix_level", "volatility"), ("DXY", "dxy_change_pct", "fx"),
        ("USD/KRW", "usd_krw_change_pct", "fx_krw"), ("WTI", "wti_change_pct", "oil"),
        ("Gold", "gold_change_pct", "gold"), ("Silver", "silver_change_pct", "silver"),
        ("BTC 24h", "btc_change_pct_24h", "crypto"), ("ETH 24h", "eth_change_pct_24h", "crypto"),
        ("ES", "es", "futures"), ("NQ", "nq", "futures"),
        ("YM", "ym", "futures"), ("RTY", "rty", "futures"),
    ]
    for label, key, kind in definitions:
        value = features.get("futures_change_pct", {}).get(key) if kind == "futures" else features.get(key)
        if value is None:
            continue
        if key in ("us10y_change_bp", "us30y_change_bp"):
            display = f"{value:+.0f}bp"
            explanation = "금리 하락은 성장주 할인율에 우호적인 방향입니다." if value < 0 else "금리 상승은 성장주 할인율 부담을 높일 수 있습니다."
        elif kind == "futures":
            display = f"{value:+.2f}%"
            cash_direction = features.get("cash_session_direction", 0)
            futures_direction = 1 if value > 0 else -1 if value < 0 else 0
            if not cash_direction or not futures_direction:
                explanation = "전일 현물 방향과의 비교 신호는 중립 또는 자료 부족입니다."
            elif futures_direction == cash_direction:
                explanation = "전일 현물 지수와 같은 방향으로 움직였습니다."
            else:
                explanation = "전일 현물 지수와 반대 방향으로 움직였습니다."
        elif kind == "volatility":
            change = features.get("vix_change_pct")
            display = f"{value:.2f} ({change:+.2f}%)" if change is not None else f"{value:.2f}"
            explanation = "변동성 기대의 수준과 변화입니다; 낮은 수준의 퍼센트 변동은 과장해서 읽지 않습니다."
        else:
            display = f"{value:+.2f}%"
            explanation = {
                "sp500": "대형주 대표 지수로 시장 방향의 기준점입니다.",
                "nasdaq": "기술·성장주 비중이 높아 금리와 대형 성장주 민감도를 반영합니다.",
                "russell": "소형주 참여를 보여줘 상승 폭이 넓은지 확인하는 보조 지표입니다.",
                "soxx": "반도체 업종의 상대 강도를 S&P와 비교해 주도 폭을 가늠합니다.",
                "fx": (
                    "달러 강세는 금융여건이 전면 완화되지 않았을 가능성을 시사합니다."
                    if value > 0 else
                    "달러 약세는 금융여건 완화와 부합하지만 금리·VIX의 동행 확인이 필요합니다."
                    if value < 0 else
                    "달러 방향은 보합입니다."
                ),
                "fx_krw": "원화 환율은 달러 흐름과 한국 투자자의 환산 수익에 함께 영향을 줍니다.",
                "oil": "급변은 물가·공급·수요 해석이 달라 원인 확인이 필요합니다.",
                "gold": "금은 달러·실질금리·안전자산 수요와 함께 봅니다.",
                "silver": "은은 귀금속 수요와 산업 경기 신호가 섞여 있습니다.",
                "crypto": "24시간 기준이며 미국 현물장 수익률과 기간이 다릅니다.",
            }.get(kind, "가격 변화입니다.")
        rows.append({"metric": label, "value": display, "interpretation": explanation})
    return rows


def _calendar_context(payload: dict, features: dict, claims: list[dict]) -> list[dict]:
    result = []
    oil_day = abs(features.get("wti_change_pct") or 0) >= 4
    rate_day = abs(features.get("us10y_change_bp") or 0) >= 5
    claim_ids = {claim["claim_id"] for claim in claims}
    for event in payload.get("econ_calendar", []):
        if not isinstance(event, dict) or event.get("error"):
            continue
        title = str(event.get("title") or event.get("event") or "")
        text = title.lower()
        importance = int(event.get("importance") or 0)
        reasons = []
        event_claims = set()
        if oil_day and any(k in text for k in ("eia", "petroleum", "oil", "crude")):
            importance = min(3, importance + 1)
            reasons.append("오늘 유가 변동폭이 커 재고·공급 확인 가치가 높습니다.")
            event_claims.update({"OIL_DISINFLATION_TAILWIND", "OIL_DEMAND_SCARE"})
        if rate_day and any(k in text for k in ("treasury", "auction", "fed", "fomc", "speech")):
            importance = min(3, importance + 1)
            reasons.append("10년 금리 변동폭이 커 금리 촉매를 확인할 필요가 있습니다.")
            event_claims.update({"RATES_TAILWIND_GROWTH", "RATES_HEADWIND_GROWTH"})
        if not reasons:
            reasons.append("일정의 기본 중요도를 유지합니다.")
        result.append({**event, "contextual_importance": importance, "why_today_matters": " ".join(reasons),
                       "related_claims": sorted(claim_ids & event_claims)})
    return sorted(result, key=lambda e: (-e["contextual_importance"], e.get("scheduled_at_kst") or e.get("scheduled_date") or ""))


EARNINGS_IMPORTANCE = {
    "NVDA": 100, "AAPL": 98, "MSFT": 97, "AMZN": 96, "GOOGL": 95, "META": 94,
    "TSLA": 92, "AMD": 90, "AVGO": 88, "MU": 85, "TSM": 84,
    "PAYX": 82, "CTAS": 80, "GIS": 72, "CBRL": 55, "SFIX": 45, "FUL": 40,
}


def _earnings_context(payload: dict, claims: list[dict]) -> dict:
    assets = set().union(*(set(c.get("affected_assets", [])) for c in claims)) if claims else set()
    items = []
    for item in payload.get("earnings", []):
        if not isinstance(item, dict) or item.get("error"):
            continue
        symbol = str(item.get("symbol") or "").upper()
        sector_bonus = 30 if symbol in {"NVDA", "AMD", "AVGO", "MU", "TSM"} and assets & {"semiconductors", "technology"} else 0
        score = EARNINGS_IMPORTANCE.get(symbol, 10) + sector_bonus
        focus = {
            "NVDA": ["데이터센터 매출·성장률", "총마진과 공급 제약", "다음 분기 가이던스"],
            "AMD": ["데이터센터 GPU 매출", "서버 CPU 점유율", "제품 램프와 마진"],
            "MU": ["HBM 출하·가격", "메모리 가격 사이클", "설비투자와 공급 규율"],
            "TSM": ["첨단 공정 수율·가동률", "AI 주문과 패키징 병목", "설비투자 가이던스"],
            "AAPL": ["iPhone 수요와 지역별 매출", "서비스 성장", "마진·가이던스"],
            "MSFT": ["Azure 성장률", "AI 투자 대비 수익화", "자본지출"],
            "AMZN": ["AWS 성장률", "광고 성장", "영업마진과 capex"],
            "GOOGL": ["검색·클라우드 성장", "AI 제품 수익화", "자본지출"],
            "META": ["광고 성장", "참여도·단가", "AI capex와 가이던스"],
        }.get(symbol, ["매출 성장", "마진", "경영진 가이던스"])
        items.append({**item, "relevance_score": score, "what_to_watch": focus})
    ranked = sorted(items, key=lambda x: (-x["relevance_score"], str(x.get("symbol", ""))))
    return {"top": ranked[:5], "other_count": max(0, len(ranked)-5)}


def build_insight(payload: dict, *, persist_queue: bool = False) -> dict:
    """Build all deterministic insight fields from existing canonical inputs."""
    features = calculate_features(payload)
    anomalies = detect_anomalies(features)
    claims = build_claims(features, anomalies, payload)
    stories = rank_and_cluster_news(payload.get("news", []), anomalies, claims)
    queue = build_research_queue(anomalies)
    if persist_queue:
        write_research_queue(queue)
    by_id = {claim["claim_id"]: claim for claim in claims}
    selected = [name for name in CLAIM_PRIORITY if name in by_id]
    selected += [name for name in by_id if name not in selected]
    movers = [CLAIM_TEXT[name] for name in selected[:5]]
    driver_claims = [by_id[name] for name in selected[:3]]
    if "SEMI_LEADERSHIP" in by_id:
        semi = features.get("soxx")
        spread = features.get("soxx_sp500_spread_pp")
        rates = features.get("us10y_change_bp")
        oil = features.get("wti_change_pct")
        semi_text = (
            f"반도체 +{semi:.1f}%가 S&P를 {spread:.1f}pp 앞섰습니다."
            if semi is not None and semi > 0 and spread is not None else
            f"반도체 {semi:+.1f}% 하락에도 S&P 대비 {spread:+.1f}pp 선방했습니다."
            if semi is not None and spread is not None else
            "반도체와 S&P의 상대 강도 차이가 커졌습니다."
        )
        rate_text = f" 10년물 {rates:+.0f}bp 하락은 성장주에 우호적입니다." if rates is not None and rates < 0 else f" 10년물 {rates:+.0f}bp 상승은 성장주 할인율 부담이 될 수 있습니다." if rates is not None and rates > 0 else ""
        oil_text = (
            f" WTI {oil:+.1f}% 급락의 공급·수요 배경은 미확인입니다."
            if oil is not None and oil <= -4 else
            f" WTI {oil:+.1f}% 급등의 공급·수요 배경은 확인이 필요합니다."
            if oil is not None and oil >= 4 else
            f" WTI {oil:+.1f}% 변동은 별도 배경 확인이 필요합니다."
            if oil is not None else ""
        )
        conclusion = semi_text + rate_text + oil_text
    else:
        conclusion = " ".join(CLAIM_TEXT[name] for name in selected[:3]) or "주요 자산의 큰 괴리가 없어 뚜렷한 단일 주도 요인은 확인되지 않았습니다."
    semi = features.get("soxx")
    spread = features.get("soxx_sp500_spread_pp")
    rates = features.get("us10y_change_bp")
    oil = features.get("wti_change_pct")
    subject_parts = []
    if semi is not None and spread is not None and spread > 0:
        subject_parts.append(f"반도체 주도(SOXX {semi:+.1f}%, 상대 {spread:+.1f}pp)" if semi > 0 else f"반도체 상대 선방(SOXX {semi:+.1f}%, spread {spread:+.1f}pp)")
    if rates is not None and rates <= -3:
        subject_parts.append(f"10Y {rates:+.0f}bp 하락")
    elif rates is not None and rates >= 3:
        subject_parts.append(f"10Y {rates:+.0f}bp 상승")
    if oil is not None and abs(oil) >= 4:
        subject_parts.append(f"WTI {oil:+.1f}% 원인 미확인")
    subject_conclusion = "; ".join(subject_parts) if subject_parts else conclusion.split("。")[0]
    watch = list(dict.fromkeys(claim["what_to_watch"] for claim in claims))[:5]
    if not watch:
        watch = ["주요 지수의 상승 폭과 장 초반 breadth", "다음 거시 일정과 금리 반응"]
    return {
        "schema_version": 1, "features": features, "anomalies": anomalies,
        "claims": claims, "conclusion": conclusion, "market_movers": movers,
        "subject_conclusion": subject_conclusion,
        "market_driver_claims": driver_claims, "market_claim_ids": list(by_id),
        "market_map": _market_map(features), "story_clusters": stories,
        "research_needed": bool(queue), "research_queue": queue,
        "economic_events": _calendar_context(payload, features, claims),
        "earnings": _earnings_context(payload, claims),
        "what_to_watch": watch, "narrative_adapter": {"interface": "render(insight, style)", "provider": None},
        "evidence_note": "시장 반응과 뉴스 동시성은 인과 증명이 아닙니다. 원인 설명은 출처로 확인될 때까지 해석으로 표시합니다.",
    }
