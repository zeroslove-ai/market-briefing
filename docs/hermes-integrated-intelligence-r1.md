# Hermes R1 Integrated Market Intelligence — Product & Analysis Authority

Status: DESIGN AUTHORITY (R1)
Scope: 기존 Hermes 4종 보고 + Sigma Intelligence + News/Event Intelligence + 설명/검증 레이어 통합
Target reader: 주식 중급자 — 기본 시장용어는 알고 있으나 여러 소스를 매일 직접 연결해 해석하기는 부담스러운 사용자

## 1. North Star

Hermes R1의 목표는 데이터를 많이 나열하는 것이 아니라, 매 보고마다 아래 다섯 질문에 답하는 것이다.

1. **무슨 일이 일어났나?** — 지수, 선물, 금리, 달러, VIX, 섹터, 종목.
2. **평소 범위와 비교하면 얼마나 특이한가?** — Weekly Sigma, daily surprise, breadth.
3. **무엇이 같이 움직였나?** — 시장/섹터/종목/OI/cross-asset confluence.
4. **왜 그런 것으로 볼 수 있나? 반대 근거는 무엇인가?** — Evidence / Counter-evidence.
5. **다음 세션에서 무엇을 확인해야 하나?** — 이벤트, ±1σ edge, OI 지속 여부, 재진입/추가 이탈.

핵심 원칙:

`raw data -> deterministic features -> evidence objects -> LLM explanation -> Telegram`

LLM은 숫자를 다시 계산하거나 원인을 창작하지 않는다.

## 2. 기존 Hermes 보고는 유지한다

현재 4개 보고의 역할을 유지하되, 같은 공통 상태를 읽도록 바꾼다.

| 보고 | 유지할 기존 내용 | R1에서 추가되는 역할 |
|---|---|---|
| 07:00 아침 | 전일 지수/금리/달러/VIX/금속/뉴스/실적/옵션 | 전일 장 사후해설, Sigma 이동, 섹터 breadth, 전일 판단 검증 |
| 21:00 저녁 | 선물/금리/달러/VIX/뉴스/경제/실적 | 아침 이후 무엇이 바뀌었는지, 오늘 밤 위험요인/경계값 |
| 장 시작 | 선물 + 전일 옵션 신호 + 이벤트 | opening watch, 이전 thesis 확인/무효화 조건 |
| 장 마감 | backdrop + OI anomaly + conviction + 결과검증 | session verdict, Sigma transition, confluence, carry-over |

기존 섹션을 삭제하지 않는다. 다만 중복 데이터 수집/서로 다른 계산은 공통 엔진으로 통합한다.

## 3. R1 아키텍처

### A. Data Plane — 사실 수집

공통 collector가 다음을 한 번 수집하고 session timestamp와 quality를 붙인다.

- Spot: S&P 500, Nasdaq, NDX, Dow, Russell, SOXX
- Futures: ES/NQ/YM/RTY
- Macro: VIX, 10Y/30Y, DXY, USD/KRW, WTI, Gold, Silver
- Equity universe prices
- CBOE options: IV/OI/Greeks
- Earnings
- Economic calendar
- News / official filings / macro releases
- Yahoo Trending

뉴스/이벤트 상세 authority는 `docs/hermes-news-intelligence-r1.md`를 따른다. 기존 CNBC RSS는 유지하고 SEC/Fed/BLS/BEA 공식 소스를 단계적으로 추가한다.

가격 정본은 Yahoo regular session. CBOE는 IV/OI/Greeks 전용이다.

### B. Feature Plane — 계산

모든 feature는 deterministic하게 만든다.

1. **Market movement**
   - index return
   - futures delta
   - yield bp move
   - VIX level/change
   - dollar/oil/metals move

2. **Sigma**
   - weekly z
   - delta-z
   - new breakout / re-entry
   - breach age
   - market/sector breadth

3. **Options**
   - call/put OI delta
   - OI anomaly
   - IV30
   - legacy 30D expected move
   - 기존 conviction breakdown

4. **Event risk**
   - earnings proximity
   - macro event proximity
   - event result vs forecast
   - important-news candidate

5. **News / Event Intelligence**
   - official-source events
   - story clustering / duplicate suppression
   - entity + sector linking
   - materiality / novelty
   - event-to-price reaction
   - news + Sigma/OI/sector context

6. **Change since previous briefing**
   - morning -> evening
   - evening -> open
   - open -> close
   - prior close -> current close

R1에서 특히 중요한 것은 절대값보다 **변화량**이다. 같은 VIX 19라도 15에서 19로 오른 것과 24에서 19로 내려온 것은 다르게 설명해야 한다.

### C. Evidence Plane — 해석 근거 묶음

LLM에게 원시 JSON 전체를 던지고 자유롭게 해석시키지 않는다. Python이 먼저 설명 가능한 evidence object를 만든다.

예:

```json
{
  "claim_id": "SEMIS_LED_WEAKNESS",
  "level": "sector",
  "subject": "Semiconductors",
  "observation": "반도체가 시장 약세를 주도",
  "support": [
    "sector_median_z=-0.88",
    "lower_break_ratio=0.41",
    "SOXX=-2.1%",
    "median_delta_z=-0.34"
  ],
  "counter_evidence": [
    "SPY weekly_z=-0.55"
  ],
  "confidence": "HIGH"
}
```

R1 기본 claim family:

- `BREADTH_DOWN / BREADTH_UP`
- `SEMIS_LED_WEAKNESS / SOFTWARE_LED_STRENGTH`
- `RISK_OFF_CONFIRMED / RISK_ON_CONFIRMED`
- `CROSS_ASSET_MIXED`
- `RATES_HEADWIND_GROWTH`
- `VOLATILITY_EXPANSION`
- `IDIOSYNCRATIC_MOVE`
- `SIGMA_OI_CONFIRMED`
- `SIGMA_OI_CONFLICT`
- `EVENT_RISK_DOMINANT`
- `REENTRY_AFTER_EXTREME`

### D. Narrative Plane — 설명

LLM은 evidence object와 deterministic 숫자를 자연어로 번역한다.

설명 순서:

1. **한 줄 결론**
2. **무슨 일이 있었는지**
3. **왜 그렇게 해석하는지**
4. **반대/혼재 신호**
5. **이전 보고 이후 달라진 점**
6. **다음 확인 포인트**
7. 필요 시 수치 상세

원인 표현 규칙:

- 관찰: 단정 가능 — “10년물 금리가 8bp 올랐다.”
- 규칙 기반 해석: 설명 가능 — “금리 상승과 성장주 약세가 같은 방향으로 나타났다.”
- 뉴스/이벤트: “촉매 후보”, “시점상 연관 가능성”으로 표현.
- 직접 확인되지 않은 인과: “때문이다” 금지.

### E. Delivery Plane

기존 Telegram 전달을 유지한다. 장기적으로 웹 UI/API는 같은 JSON을 읽는다.

## 4. 단순 점수보다 설명 가능한 상태를 우선한다

기존 `market_backdrop -100~100`과 `conviction 0~100`은 호환성을 위해 유지하되 R1의 핵심 판단은 아니다.

R1 market state는 다음처럼 분해한다.

```json
{
  "direction": "down",
  "breadth": "broad_down",
  "volatility": "expanding",
  "rates_impulse": "tightening",
  "usd_impulse": "stronger",
  "cross_asset_confirmation": "mixed",
  "confidence": "MEDIUM"
}
```

이렇게 하면 “점수 -47이라 bearish”보다 왜 약세인지 설명할 수 있다.

기존 conviction도 최종 숫자뿐 아니라 breakdown을 노출한다.

```json
{
  "legacy_score": 72,
  "evidence": {
    "oi": 28,
    "price": 20,
    "iv": 14,
    "legacy_sigma_bonus": 10
  },
  "weekly_sigma": {
    "z": -1.22,
    "delta_z": -0.41
  },
  "sector_confirmation": true
}
```

## 5. 보고 간 기억 — Snapshot Delta

현재 4개의 보고는 서로 독립된 스냅샷에 가깝다. R1은 각 보고 결과를 저장해 **“그 사이 무엇이 변했는가”**를 계산한다.

제안:

```text
state/report_snapshots/
  latest_morning.json
  latest_evening.json
  latest_open.json
  latest_close.json
state/report_history/YYYY-MM-DD.jsonl
```

예:

- 07:00: NQ +0.6%, VIX 17.2
- 21:00: NQ -0.1%, VIX 19.0

Hermes 설명:

“아침 이후 분위기가 악화됐습니다. 나스닥 선물은 +0.6%에서 -0.1%로 뒤집혔고 VIX는 17.2에서 19.0으로 상승했습니다.”

이 변화 설명이 R1의 핵심 가치다.

## 6. 4개 보고의 R1 역할

### 07:00 — Close Autopsy / 아침 보고

목적: 전일 미국장을 ‘복기’한다.

순서:

1. 30초 요약
2. 전일 지수와 주요 자산
3. 시장 내부 breadth / Sigma distribution
4. 강/약 섹터
5. 새 Sigma breakout/re-entry
6. OI confluence
7. 뉴스/실적/경제지표 중 설명 가능한 catalyst candidate
8. 전일 관전 포인트의 결과
9. 다음 미국장 carry-over

질문: **어제 실제로 무슨 일이 일어났고 무엇이 남았나?**

### 21:00 — Setup / 저녁 보고

목적: 미국장 시작 전에 오전 보고 이후 바뀐 것을 정리한다.

순서:

1. 아침 이후 변화
2. 선물/금리/DXY/VIX
3. 당일 핵심 실적/경제 이벤트
4. ±1σ edge 근접 종목
5. 전일 OI/Sigma 신호의 현재 상태
6. 오늘 밤 확인 조건

질문: **오늘 밤 무엇이 달라질 수 있고 어디를 보면 되나?**

### Opening — Opening Watch

목적: 장 시작 시점에서 사전 setup이 맞는지 확인한다.

- premarket/futures dislocation
- regular_z와 indicative_z 분리
- opening gap 후보
- 이벤트 직후 종목
- prior thesis confirm / invalidate 조건

질문: **장 시작에서 무엇이 실제로 확인되고 무엇이 깨졌나?**

### 05:05 — Session Verdict / 마감 보고

목적: 오늘의 최종 상태변화를 기록한다.

1. 시장 verdict
2. breadth 변화
3. sector rotation
4. Sigma transition
5. OI anomaly/confluence
6. 전일/장전 thesis 검증
7. 지속할 watch / 폐기할 watch
8. 다음 세션 carry-over

질문: **오늘 무엇이 확정됐고, 무엇은 아직 미확정인가?**

## 7. 중급 투자자가 읽기 좋은 설명 구조

한 보고를 3층으로 만든다.

### Layer 1 — 30초 요약

핵심 용어는 숨기지 않되, 수치가 의미하는 시장 메커니즘을 한 문장으로 붙인다. 단순 교과서 정의보다 ‘현재 시장에서 왜 중요한가’를 설명한다.

예:

“오늘은 지수보다 시장 내부가 더 약했습니다. 특히 반도체에서 예상범위를 벗어난 하락 종목이 늘었고, 일부는 풋 OI 증가도 같이 나타났습니다.”

### Layer 2 — 왜?

용어를 바로 번역한다.

“NVDA -1.2σ는 ‘이번 주 옵션시장이 예상한 하단 이동거리보다 약 20% 더 내려갔다’는 뜻입니다.”

### Layer 3 — 근거

원하면 확인할 숫자.

“NVDA -1.22σ / Δz -0.41 / put OI +18% / semiconductor median -0.84σ”

기본 Telegram은 Layer 1+2 중심, 중요한 후보만 Layer 3를 붙인다.

중급자 설명 표준 예:

- `10Y +8bp` -> “장기 할인율 압력이 커져 고밸류 성장주에 부담이 될 수 있는 방향”
- `VIX 15 -> 19` -> “절대수준은 극단적 공포가 아니지만 위험 프리미엄이 빠르게 확대”
- `breadth 하락` -> “지수보다 개별 종목 약세가 넓어져 지수 표면보다 내부가 취약”
- `-1.2σ` -> “이번 주 옵션 기대 하단거리보다 약 20% 더 내려온 상태”
- `put OI +18%` -> “하방 옵션 포지셔닝 관심이 커진 흔적이지만 신규 숏으로 확정할 수는 없음”
- `ticker +4%, sector +1%` -> “시장 전체보다 해당 종목 고유 재료가 강했을 가능성을 높이는 relative strength”

## 8. 데이터 품질과 현재 반드시 고칠 문제

현재 코드에서 R1 전에 해결할 데이터 무결성 이슈:

1. **us_market_report의 CBOE 가격 사용**
   - 옵션 섹션에서 CBOE `current_price` / `price_change_percent`를 사용 중.
   - 정본 정책과 충돌. Yahoo regular price로 교체.

2. **아침/저녁 OI snapshot 오염**
   - `us_market_report.py`가 실행될 때마다 `oi_snapshot.json`을 갱신한다.
   - 하루 두 번 실행하면 ‘전일 대비’가 실제 전일 close가 아니라 직전 실행 대비가 될 수 있다.
   - OI snapshot owner를 close job으로 단일화하고 `session_date`를 저장한다.

3. **state 경로 불일치**
   - 문서는 `state/`를 정본으로 쓰지만 현재 스크립트 일부는 script directory에 저장.
   - repo-root state helper로 통일.

4. **시간대 하드코딩**
   - option flow는 EDT UTC-4를 하드코딩.
   - `ZoneInfo("America/New_York")`로 변경.

5. **Yahoo candle date의 UTC 표기**
   - regular session label은 ET date 기준으로 정규화.

6. **실적 target date**
   - KST 시스템의 `date.today()`가 아니라 ‘다음/현재 미국 세션 날짜’를 명시적으로 계산.

7. **중복 네트워크 호출**
   - 같은 실행에서 Yahoo/CBOE를 여러 스크립트가 반복 호출.
   - session snapshot/cache를 공유해 CBOE 429 위험 감소.

8. **DST cron 수동 변경**
   - scheduler가 timezone을 지원하면 America/New_York 기반.
   - 지원하지 않으면 EDT/EST 두 KST 슬롯을 등록하고 wrapper가 실제 NY phase를 확인해 한 번만 실행.

## 9. R1 데이터 계약

공통 상위 payload:

```json
{
  "meta": {
    "generated_at_kst": "...",
    "market_session_date": "...",
    "phase": "morning|evening|open|close",
    "data_quality": []
  },
  "market": {},
  "cross_asset": {},
  "events": {},
  "news": {
    "clusters": [],
    "official_events": [],
    "since_previous_report": [],
    "stats": {}
  },
  "sigma": {},
  "options": {},
  "changes_since_previous_report": {},
  "evidence": [],
  "watchlist": [],
  "legacy": {}
}
```

`legacy` 아래에는 기존 backdrop/conviction 등 호환 필드를 유지할 수 있다.

## 10. Evidence confidence

R1에서는 확률처럼 보이는 가짜 정밀도를 만들지 않는다.

- HIGH: 독립된 3개 이상 축이 같은 방향 + 주요 반대근거 없음
- MEDIUM: 2개 축 동조 또는 3개 축 동조지만 반대근거 존재
- LOW: 한 축 중심 또는 데이터 품질 제한

독립 축 예:

- price/sigma
- sector breadth
- options OI
- cross-asset
- event/news timing

같은 원천에서 파생된 두 숫자를 독립 증거 두 개로 세지 않는다.

## 11. 역사 검증

초기에는 예측 모델을 만들지 않는다. 먼저 조건별 결과를 축적한다.

저장:

- `SIGMA_ONLY`
- `OI_ONLY`
- `SIGMA_OI_CONFIRMED`
- `BREADTH_CONFIRMED`
- `REENTRY`
- `EXTREME`

각 이벤트의 +1/+3/+5 session forward return, 최대 상승/하락, 재진입 여부를 저장한다.

최소 표본 전에는 threshold를 자주 변경하지 않는다. R1 목표는 ‘잘 설명되는 상태 기록’이지 과최적화된 매매모델이 아니다.

## 12. 구현 순서

### R1-0 Data Integrity Foundation — 가장 먼저

- timezone/session helper
- repo-root state helper
- common Yahoo quote
- common CBOE chain parser/cache
- OI snapshot ownership
- Yahoo price authority
- target US session date
- report snapshot history
- 기존 4 reports regression

### R1-1 Weekly Sigma Core

기존 Sigma S1 authority대로:

- Friday Freeze
- daily z/state
- breadth
- sector
- history

### R1-2 News / Event Intelligence

- 기존 CNBC RSS 보존
- SEC EDGAR filings
- Fed releases/speeches
- BLS/BEA macro official sources
- entity linking
- dedup/story clustering
- materiality/novelty
- price/Sigma/OI reaction linking

### R1-3 Evidence Engine

- market regime component
- cross-asset rules
- evidence/counter-evidence
- confidence
- change-since-last-report
- watch ranking

### R1-4 Four-report Integration

- 07:00 close autopsy
- 21:00 setup
- opening watch
- 05:05 session verdict
- 기존 섹션 유지
- 초보자 Layer 1/2 + 필요 시 Layer 3

### R1-5 Validation

- legacy regression
- historical condition tracking
- stale/holiday/DST tests
- explanation hallucination tests

### R1-6 S2+

- gamma concentration proxy
- dashboard/API
- richer historical analytics

## 13. 완료 기준

Hermes R1 PASS 조건:

- 기존 4개 보고의 정보가 사라지지 않는다.
- 같은 세션 데이터는 공통 snapshot을 사용한다.
- 가격/OI session date가 명확하다.
- 아침 -> 저녁 -> open -> close 변화가 계산된다.
- Weekly Sigma와 기존 30D expected move가 혼용되지 않는다.
- 시장/섹터/종목/OI/cross-asset/공식 뉴스·이벤트 근거를 함께 설명한다.
- 설명에 counter-evidence가 포함될 수 있다.
- LLM이 없는 숫자를 만들지 않는다.
- 원인 미확인 시 인과관계를 단정하지 않는다.
- 중급 투자자가 30초 요약만 읽어도 시장 구조와 핵심 촉매를 파악할 수 있다.
- 전문용어는 유지하되 의미·메커니즘·한계를 함께 설명한다.
- 같은 보고에서 근거 숫자와 공식 source를 확인할 수 있다.

## 14. 제품 정의 한 문장

**Hermes R1은 시장 데이터를 나열하는 봇이 아니라, 이전 보고 이후 무엇이 바뀌었는지 추적하고, 가격·옵션·섹터·거시자산·이벤트의 근거를 교차검증해 사람이 이해할 수 있는 말로 설명하는 시장 상태 분석기다.**
