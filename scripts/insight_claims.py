"""Deterministic claim families with explicit support, counter-evidence and caveats."""

from __future__ import annotations


def build_claims(features: dict, anomalies: list[dict], payload: dict) -> list[dict]:
    f = features
    claims = []

    def add(name, condition, support, counter, assets, watch, confidence="MEDIUM"):
        if condition:
            claims.append({
                "claim_id": name, "support": support, "counter_evidence": counter,
                "confidence": confidence, "affected_assets": assets, "what_to_watch": watch,
                "interpretation_type": "evidence_backed_interpretation",
            })
    def pct(value):
        return f"{value:+.2f}%" if isinstance(value, (int, float)) else "자료 없음"
    def bp(value):
        return f"{value:+.0f}bp" if isinstance(value, (int, float)) else "자료 없음"
    def level(value):
        return f"{value:.2f}" if isinstance(value, (int, float)) else "자료 없음"

    sp, ndx, rut, soxx = (f.get(k) for k in ("sp500", "nasdaq_composite", "russell_2000", "soxx"))
    add("SEMI_LEADERSHIP", soxx is not None and sp is not None and soxx - sp >= 1.0,
        [f"SOXX {pct(soxx)} vs S&P {pct(sp)} (spread {(soxx-sp):+.2f}pp)" if soxx is not None and sp is not None else "SOXX/S&P 자료 없음"],
        [f"Russell {pct(rut)}" if rut is not None and soxx is not None and rut < soxx else "업종 breadth 자료 없음"],
        ["semiconductors", "technology"], "반도체 강세가 다른 업종과 동등가중 지수로 확산되는지")
    add("SMALL_CAP_LAG", rut is not None and ndx is not None and ndx - rut >= 1.0,
        [f"Nasdaq {pct(ndx)}가 Russell {pct(rut)}를 상회"],
        [f"S&P {pct(sp)}" if sp is not None else "S&P 자료 없음"],
        ["small_caps", "growth"], "Russell의 후속 참여와 시장 상승 종목 수")
    add("NARROW_GROWTH_RISK_ON", ndx is not None and sp is not None and rut is not None and ndx > 0 and ndx-sp >= 1.0 and ndx-rut >= 1.0,
        [f"Nasdaq 상승 및 S&P 대비 {ndx-sp:.2f}pp 우위", f"Russell 대비 {ndx-rut:.2f}pp 우위"] if None not in (ndx, sp, rut) else ["주요 지수 breadth 자료 없음"],
        [f"Russell {pct(rut)}" if rut is not None and ndx is not None and rut < ndx else "중소형주 동반 강세"],
        ["growth", "semiconductors", "small_caps"], "기술주 상승이 경기민감·소형주로 넓어지는지")
    add("BROAD_RISK_ON", all(x is not None and x > 0 for x in (sp, ndx, rut)) and f.get("cross_asset_confirmation_count", 0) >= 4,
        [f"주요 지수 모두 상승; cross-asset 확인 {f.get('cross_asset_confirmation_count', 0)}개"],
        ["SOXX/지수 breadth 또는 외환·변동성 반대 신호 확인 필요"],
        ["equities", "risk_assets"], "상승 종목 폭과 변동성·달러의 동행 여부", "HIGH")
    add("RISK_OFF_CONFIRMED", all(x is not None and x < 0 for x in (sp, ndx, rut)) and
        (f.get("vix_change_pct") or 0) > 0 and (f.get("us10y_change_bp") or 0) > 0,
        ["주요 주가지수 약세", "VIX와 10년 금리 상승이 동반"],
        ["금리 상승 원인과 안전자산 수요는 별도 확인 필요"],
        ["equities", "rates", "volatility"], "낙폭 확산 및 크레딧·달러 반응", "HIGH")
    mixed = ((f.get("dxy_change_pct") or 0) > 0 or (f.get("vix_change_pct") or 0) >= 0) and (sp or 0) > 0 and (f.get("wti_change_pct") or 0) < 0
    add("CROSS_ASSET_MIXED", mixed,
        ["주식은 상승했지만 달러 또는 VIX가 하락 확인을 제공하지 않음", f"WTI {pct(f.get('wti_change_pct'))}"],
        ["주요 주가지수 상승은 위험선호와 일치"],
        ["equities", "dollar", "volatility", "oil"], "달러·VIX와 유가가 다음 세션에도 같은 방향인지")
    add("RATES_TAILWIND_GROWTH", f.get("us10y_change_bp") is not None and f["us10y_change_bp"] <= -3 and ndx is not None and ndx > 0,
        [f"미 10년물 {bp(f.get('us10y_change_bp'))} 하락", f"Nasdaq {pct(ndx)} 상승"],
        ["금리 하락의 원인과 실질금리 자료는 미확인"],
        ["growth", "rates"], "실질금리와 장기물 입찰·연준 발언")
    add("RATES_HEADWIND_GROWTH", f.get("us10y_change_bp") is not None and f["us10y_change_bp"] >= 3 and ndx is not None and ndx < 0,
        [f"10년물 {bp(f.get('us10y_change_bp'))} 상승", f"Nasdaq {pct(ndx)} 하락"],
        ["동일 세션의 금리 민감 업종 breadth 필요"],
        ["growth", "rates"], "실질금리·연준 발언과 성장주 상대수익")
    add("VOLATILITY_EXPANSION", f.get("vix_level") is not None and f.get("vix_change_pct") is not None and f["vix_change_pct"] >= 8,
        [f"VIX {level(f.get('vix_level'))}, {pct(f.get('vix_change_pct'))}"],
        ["VIX 수준이 낮은 구간이면 변화율만으로 스트레스 강도를 단정할 수 없음"],
        ["equities", "volatility"], "VIX가 상승을 유지하는지와 지수 breadth")
    oil = f.get("wti_change_pct")
    add("OIL_DISINFLATION_TAILWIND", oil is not None and oil <= -4 and (sp or 0) > 0,
        [f"WTI {pct(oil)}", "주식시장은 상승"],
        ["공급 완화와 수요 둔화 중 원인은 확인되지 않음"],
        ["oil", "inflation_sensitive_assets"], "EIA 재고·공급 뉴스와 원유곡선")
    add("OIL_DEMAND_SCARE", oil is not None and oil <= -4 and sp is not None and sp < 0 and rut is not None and rut < 0,
        [f"WTI {pct(oil)}", "주식 및 소형주 동반 약세"],
        ["유가 공급 측면 뉴스는 별도 확인 필요"],
        ["oil", "cyclicals"], "EIA 수요·재고 지표와 경기민감주 반응")
    add("CRYPTO_CONFIRMATION", f.get("btc_change_pct_24h") is not None and f["btc_change_pct_24h"] > 0 and f.get("cross_asset_confirmation_count", 0) >= 3,
        [f"BTC 24h {pct(f['btc_change_pct_24h'])}"],
        ["crypto는 24h 기준이라 주식 정규장과 비교창이 다름"],
        ["crypto", "risk_assets"], "BTC·ETH가 주식 위험선호와 계속 동행하는지")

    if anomalies and f.get("futures_vs_cash_direction") == "diverging":
        claims.append({"claim_id": "FUTURES_DIVERGENCE", "support": ["선물 방향이 직전 현물 세션과 다름"],
                       "counter_evidence": ["선물은 낮은 유동성 구간일 수 있음"], "confidence": "LOW",
                       "affected_assets": ["equity_futures"], "what_to_watch": "현물 개장 전 선물 방향의 지속 여부",
                       "interpretation_type": "evidence_backed_interpretation"})

    # Optional Sigma/OI confluence appears only when source snapshots provide usable values.
    sigma = payload.get("sigma") or {}
    oi = payload.get("oi_anomalies") or []
    if sigma and oi:
        claims.append({"claim_id": "SIGMA_OI_CONFIRMED", "support": ["Sigma state and OI anomaly are both present"],
                       "counter_evidence": ["OI alone does not identify trade intent"], "confidence": "MEDIUM",
                       "affected_assets": list(sigma.get("symbols", [])), "what_to_watch": "price acceptance near the relevant Sigma band",
                       "interpretation_type": "evidence_backed_interpretation"})
    elif sigma and payload.get("oi_anomalies") is not None:
        claims.append({"claim_id": "SIGMA_OI_CONFLICT", "support": ["Sigma state exists but no aligned OI anomaly is present"],
                       "counter_evidence": ["OI coverage may be incomplete"], "confidence": "LOW",
                       "affected_assets": list(sigma.get("symbols", [])), "what_to_watch": "subsequent OI snapshot and price response",
                       "interpretation_type": "evidence_backed_interpretation"})
    return claims
