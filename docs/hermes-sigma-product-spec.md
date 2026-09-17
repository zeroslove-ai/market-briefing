# Hermes Sigma Intelligence — Product & Calculation Spec (R0)

Status: DESIGN AUTHORITY (R0)
Scope: 설계/연구 문서. Production 코드 변경 없음.

## 1. 목표

Hermes에 Sigma Dashboard식의 "주간 옵션 기대범위에서 현재 가격이 어디에 있는지"를 계산하는 공통 분석 레이어를 추가한다. 목적은 종목 추천이 아니라 시장 상태를 동일 척도로 설명하는 것이다.

핵심 질문은 다섯 가지다.

1. 지금 가격은 이번 주 옵션시장이 예상한 범위의 어디에 있는가?
2. 그 위치는 어제보다 빠르게 위/아래로 이동 중인가?
3. 시장 전체와 해당 섹터도 같은 방향인가?
4. 기존 OI/옵션 신호가 같은 방향으로 동조하는가?
5. 중요한 옵션 strike의 gamma concentration이 ±1σ 경계와 겹치는가?

## 2. 기존 Hermes와의 관계

기존 Hermes의 30D expected move / sigma_breakout은 유지한다. 다만 아래 세 개를 명확히 분리한다.

- `daily_surprise_sigma`: 오늘 하루 움직임이 일간 기대변동 대비 얼마나 큰가.
- `weekly_position_sigma`: 금요일에 freeze한 다음 주 기대범위 대비 현재 가격 위치.
- `expected_move_30d`: 기존 IV30 기반 30일 기대변동폭.

세 값은 시간축이 다르므로 혼용하지 않는다.

## 3. Weekly Sigma 정본

### 3.1 Friday Freeze

매주 마지막 미국 정규장 종료 후 종목별로 다음 값을 저장한다.

- `anchor_date`
- `anchor_price`: Yahoo 정규장 종가
- `expiry`: 다음 주 기준 만기
- `days_to_expiry`
- `atm_strike`
- `atm_iv`: CBOE 옵션체인에서 ATM 근처 IV
- `weekly_sigma_pct`
- `lower_1sigma`
- `upper_1sigma`

R0 계산식:

```text
weekly_sigma_pct = atm_iv * sqrt(days_to_expiry / 365)
upper_1sigma = anchor_price * (1 + weekly_sigma_pct)
lower_1sigma = anchor_price * (1 - weekly_sigma_pct)
```

금요일 freeze 이후에는 같은 주 동안 band를 재계산하지 않는다. 월~금 가격만 이동한다.

### 3.2 Daily Position

```text
z_score = ((current_price / anchor_price) - 1) / weekly_sigma_pct
```

예시:

- `z = +0.4`: 상단 방향으로 1σ 폭의 40% 이동
- `z = -0.8`: 하단 방향으로 1σ 폭의 80% 이동
- `z = -1.2`: 금요일에 옵션시장이 암시한 하단 1σ 범위를 20% 초과

### 3.3 상태값

R0 기본 상태:

- `EXTREME_UP`: z >= +1.5
- `UPPER_BREAK`: +1.0 <= z < +1.5
- `NORMAL`: -1.0 < z < +1.0
- `LOWER_BREAK`: -1.5 < z <= -1.0
- `EXTREME_DOWN`: z <= -1.5

추가 UI/브리핑용 플래그:

- `near_upper_edge`: +0.85 <= z < +1.0
- `near_lower_edge`: -1.0 < z <= -0.85
- `reentered`: 전일 |z| >= 1 이었다가 오늘 |z| < 1
- `new_breakout`: 전일 |z| < 1 이었다가 오늘 |z| >= 1

## 4. State Transition

같은 -1.2σ라도 경로가 다르면 의미가 다르다. 따라서 위치뿐 아니라 상태 변화를 저장한다.

필수 필드:

- `z_score`
- `prev_z_score`
- `delta_z`
- `breach_age_sessions`
- `max_abs_z_this_week`
- `new_breakout`
- `reentered`

R0 파생 분류 예:

- `accelerating_down`: delta_z <= -0.25
- `accelerating_up`: delta_z >= +0.25
- `persistent_lower_break`: z <= -1 and breach_age_sessions >= 2
- `persistent_upper_break`: z >= +1 and breach_age_sessions >= 2

수치는 초기값이며 히스토리 축적 후 보정한다.

## 5. Cross-sectional Market Breadth

종목별 z를 단순 나열하지 않고 시장 전체 분포를 요약한다.

필수 집계:

- universe count
- mean z / median z
- count(z >= +1)
- count(z <= -1)
- count(z >= +1.5)
- count(z <= -1.5)
- count(near +1 / near -1)
- positive/negative skew 간단 요약
- sector median z
- sector mean z
- sector breach ratio

시장 해설은 예를 들어 다음처럼 생성한다.

```text
지수 자체는 아직 1σ 안이지만 하단 이탈 종목 수가 상단 이탈보다 크게 많다.
→ 시장 전체가 붕괴했다고 단정할 단계는 아니지만 내부 breadth는 하방으로 기울어 있다.
```

## 6. Sector Layer

R0에서는 추적 종목에 고정 `sector`/`group` mapping을 둔다.

예:

- Semiconductors
- Software / Cloud
- Cybersecurity
- Mega-cap Internet
- Fintech / Crypto
- Financials
- Industrials
- Consumer
- Energy
- Healthcare

섹터별로 `median_z`, `breach_ratio`, `delta_median_z`를 계산한다.

## 7. OI / 기존 신호와의 Confluence

Sigma는 방향 추천기가 아니다. 기존 OI anomaly와 결합해 상황을 설명한다.

R0 confluence class:

- `SIGMA_ONLY`: sigma 이탈, OI 동조 없음
- `OI_ONLY`: OI anomaly, sigma 이탈 없음
- `CONFIRMED`: sigma 방향과 OI/가격 방향이 일치
- `CONFLICT`: sigma 위치와 OI signal 방향이 반대
- `BREADTH_CONFIRMED`: CONFIRMED + 동일 섹터도 같은 방향으로 크게 기울어 있음

예:

```text
NVDA -1.18σ / put OI +18% / SOXX sector median -0.82σ
→ 개별 하단 이탈 + 옵션 포지셔닝 + 섹터 약세가 동조하는 구조
```

이 표현은 투자 매수/매도 지시가 아니라 상태 설명이다.

## 8. Gamma Concentration Proxy (S2)

S1의 필수 범위가 아니다. S2에서 CBOE의 strike별 `gamma`와 `open_interest`를 사용한다.

초기 proxy:

```text
gamma_weight = abs(gamma) * open_interest * 100
```

주의: 공개 체인만으로 dealer의 실제 long/short inventory를 확정할 수 없다. 따라서 출력명은 `dealer GEX`가 아니라 다음 중 하나로 제한한다.

- `gamma concentration`
- `GEX proxy`
- `gamma-weighted OI`

후보 reaction zone:

- ±1σ edge와 strike 거리 <= 0.5%
- 해당 strike gamma_weight가 인근 합계의 >= 15%
- 2위 strike 대비 >= 2x

위 threshold는 참고 사이트 구조에서 착안한 초기값이며 백테스트 후 보정한다.

## 9. 데이터 소스 정책

- 가격/정규장 OHLC 정본: Yahoo chart
- IV/OI/Greeks: CBOE delayed options
- 뉴스/경제/실적: 기존 Hermes 소스 유지

CBOE `current_price`는 가격 정본으로 쓰지 않는다.

CBOE rate limit 때문에 주간 band build는 순차 호출 + 백오프를 유지한다. Daily position 계산은 저장된 freeze 값 + Yahoo 가격만으로 계산하여 CBOE 호출을 최소화한다.

## 10. 시간대 정책

기존 고정 UTC-4 timezone을 production 구현 시 제거하고 `zoneinfo.ZoneInfo("America/New_York")`를 사용한다.

- 미국 세션 기준: America/New_York
- 사용자 전달 기준: Asia/Seoul
- DST 수동 하드코딩 금지

## 11. 데이터 모델

`state/sigma_week.json`

```json
{
  "week_id": "2026-W38",
  "frozen_at_et": "2026-09-18T16:10:00-04:00",
  "method_version": "sigma-r0",
  "symbols": {
    "NVDA": {
      "sector": "Semiconductors",
      "anchor_date": "2026-09-18",
      "anchor_price": 0,
      "expiry": "2026-09-25",
      "days_to_expiry": 7,
      "atm_strike": 0,
      "atm_iv": 0,
      "weekly_sigma_pct": 0,
      "lower_1sigma": 0,
      "upper_1sigma": 0
    }
  }
}
```

`state/sigma_history.jsonl` 또는 향후 SQLite:

```json
{"date":"2026-09-21","ticker":"NVDA","price":0,"z_score":-0.62,"delta_z":-0.21,"status":"NORMAL","breach_age_sessions":0}
```

## 12. 출력 JSON 계약

`sigma_engine.py daily` 출력 최상위:

```json
{
  "generated_at": "...",
  "week_id": "...",
  "market_summary": {},
  "sector_summary": [],
  "symbols": [],
  "watchlist": {
    "new_breakouts": [],
    "near_edges": [],
    "reentries": [],
    "fast_movers": []
  }
}
```

LLM은 계산하지 않는다. LLM은 이 deterministic JSON을 자연어로 설명만 한다.

## 13. S1 완료 조건

S1은 다음까지다.

1. 약 100개 추적 종목 Friday Freeze
2. ATM IV 기반 weekly band 저장
3. 매일 z-score 계산
4. 5-state status
5. new breakout / re-entry / delta-z / breach age
6. market breadth
7. sector breadth
8. previous-week history
9. JSON output contract
10. unit test / fixture 기반 계산 검증

S1에 포함하지 않는다.

- 웹 UI
- 매매 추천
- dealer positioning 단정
- 복잡한 ML
- intraday streaming

## 14. 핵심 원칙

`계산은 deterministic, 해설은 LLM.`

Hermes가 숫자를 창작하거나 시그마를 재계산하지 않는다. Python이 만든 상태값을 받아 "무슨 일이 일어나고 있는지"만 설명한다.
