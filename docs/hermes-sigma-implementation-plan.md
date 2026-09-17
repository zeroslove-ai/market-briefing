# Hermes Sigma Intelligence — Implementation Plan

Status: IMPLEMENTATION AUTHORITY (R0)

이 문서는 Codex/Claude/GPT가 바로 개발에 들어갈 수 있도록 작업 순서, 파일 구조, 테스트 기준을 정의한다.

## 1. 개발 원칙

- 기존 브리핑 파이프라인을 깨지 않는다.
- 계산 로직은 Python deterministic.
- LLM은 계산 결과를 해설만 한다.
- Sigma S1 완료 전 웹 UI를 만들지 않는다.
- 무료 데이터만 사용한다.
- 가격 정본은 Yahoo 정규장.
- 옵션 IV/OI/Greeks는 CBOE delayed options.
- CBOE 호출 최소화.
- DST를 코드에 숫자로 하드코딩하지 않는다.

## 2. 제안 파일 구조

```text
scripts/
  sigma_engine.py
  sigma_build_week.py
  sigma_daily.py
  sigma_shared.py
  option_flow_report.py
  us_market_report.py

state/
  sigma_week.json
  sigma_previous_week.json
  sigma_history.jsonl
  sigma_daily_latest.json

config/
  sigma_universe.json
  sector_map.json

tests/
  fixtures/
    cboe_option_chain_sample.json
    yahoo_quote_sample.json
    sigma_week_sample.json
  test_sigma_math.py
  test_sigma_state.py
  test_sigma_breadth.py

docs/
  hermes-sigma-product-spec.md
  hermes-sigma-explainer.md
  hermes-sigma-implementation-plan.md
  hermes-sigma-ai-handoff.md
```

현재 repo에 `config/`, `tests/`가 없다면 S1에서 새로 만든다.

## 3. 단계별 구현

### S1-A. 공통 기반 정리

#### 작업

1. `ZoneInfo("America/New_York")`, `ZoneInfo("Asia/Seoul")` 도입
2. state path helper 통일
3. Yahoo/CBOE 공통 fetch 유틸 정리
4. symbol universe와 sector mapping 외부 config 분리

#### 완료 기준

- 기존 4개 브리핑 코드 동작 유지
- DST 수동 offset 제거 가능 구조
- state 파일이 모두 repo root의 `state/` 아래로 저장됨

### S1-B. Friday Freeze Builder

파일:

- `scripts/sigma_build_week.py`
- `scripts/sigma_shared.py`

#### 입력

- 추적 종목 universe
- Yahoo 정규장 종가
- CBOE option chain

#### ATM IV 선택 R0

1. 기준 만기 선택: 다음 주 목표 expiry
2. current/anchor price에 가장 가까운 strike 후보 찾기
3. 동일 strike의 call/put IV가 모두 있으면 평균
4. 한쪽만 있으면 해당 IV 사용 + quality flag
5. IV 누락/0/비정상값이면 symbol 제외 또는 fallback flag

#### days_to_expiry

R0은 달력일 기준:

```text
(expiry_date - anchor_date).days
```

나중에 trading-day convention과 비교 가능하도록 `method_version`을 저장한다.

#### 출력

`state/sigma_week.json`

#### 검증

- 모든 symbol에 anchor_price > 0
- atm_iv 범위 sanity check
- lower < anchor < upper
- weekly_sigma_pct > 0
- week_id / expiry / method_version 필수

### S1-C. Daily Z Engine

파일:

- `scripts/sigma_daily.py`

#### 입력

- `sigma_week.json`
- Yahoo current regular market price
- 전일 sigma daily state

#### 계산

```text
z_score
status
delta_z
new_breakout
reentered
breach_age_sessions
max_abs_z_this_week
edge_distance_z
```

#### edge_distance_z

```text
to_upper = 1 - z
to_lower = z + 1
```

상단/하단 중 가까운 쪽을 별도 field로 저장한다.

### S1-D. Breadth Engine

함수는 `sigma_shared.py` 또는 `sigma_engine.py`에 둔다.

#### market summary

```json
{
  "count": 100,
  "mean_z": -0.31,
  "median_z": -0.38,
  "upper_break_count": 4,
  "lower_break_count": 15,
  "extreme_up_count": 1,
  "extreme_down_count": 5,
  "near_upper_count": 3,
  "near_lower_count": 9,
  "breadth_bias": "down"
}
```

#### breadth_bias R0

초기 deterministic 규칙:

- lower_break_count - upper_break_count >= max(5, universe*0.08): `down`
- reverse: `up`
- else `balanced`

추후 history로 보정.

#### sector summary

각 sector에:

- count
- mean_z
- median_z
- breach_up_count
- breach_down_count
- breach_ratio
- delta_median_z

### S1-E. Watchlist Engine

자동 추출 목록:

- `new_breakouts`
- `new_reentries`
- `near_edges`
- `fast_movers`
- `persistent_breaks`
- `extremes`

초기 fast mover 기준:

```text
abs(delta_z) >= 0.30
```

threshold는 config로 분리한다.

### S1-F. Previous Week Comparison

주간 freeze rollover 시 기존 `sigma_week.json`을 `sigma_previous_week.json`으로 보존한다.

종목별 비교:

- previous_week_final_z
- current_week_z
- previous_week_max_abs_z
- repeated_break_direction

예:

```text
이번 주도 -1σ를 하향 이탈했고 지난주에도 같은 방향으로 이탈
```

단, 이것을 추세 지속 확률로 해석하지 않는다.

## 4. 기존 Option Flow와 결합

S1 core가 안정된 뒤 S1-G 또는 S2에서 결합한다.

`option_flow_report.py`가 sigma latest JSON을 읽고 기존 signal에 다음을 병합한다.

```json
{
  "weekly_z": -1.18,
  "sigma_status": "LOWER_BREAK",
  "delta_z": -0.42,
  "sector_median_z": -0.81,
  "confluence": "BREADTH_CONFIRMED"
}
```

OI signal 자체 계산식은 S1에서 변경하지 않는다.

## 5. Gamma Concentration S2

별도 파일 권장:

`scripts/gamma_proxy.py`

### R0 proxy

계약별:

```text
gamma_weight = abs(gamma) * open_interest * 100
```

strike별 call/put 합산 후 인근 strike 분포 계산.

### 출력

```json
{
  "ticker": "NVDA",
  "strike": 200,
  "gamma_weight": 123456,
  "local_share": 0.19,
  "second_ratio": 2.4,
  "distance_to_lower_1sigma_pct": 0.32,
  "reaction_zone_candidate": true
}
```

### 용어

- dealer wall 금지
- confirmed support/resistance 금지
- gamma concentration / GEX proxy 사용

## 6. Cron 설계

### Weekly Build

미국 금요일 장 마감 데이터 확정 후 실행.

권장 개념:

```text
Friday close + 10~20 min
```

KST 시각을 고정 숫자로 문서화하지 말고 ET-aware scheduler 또는 DST 대응 값을 사용한다.

### Daily Close

기존 05:05 KST 브리핑 흐름에서 sigma daily를 먼저 실행하고 이후 옵션플로우 보고가 그 JSON을 읽는다.

개념 순서:

```text
1. sigma_daily.py
2. option_flow_close.py
3. LLM briefing
4. Telegram
```

### Premarket / Open

프리마켓에서는 freeze band는 그대로 두고 프리마켓 가격 기반 위치를 별도 field로 만들 수 있다.

S1에서는 정규장 정본과 혼동 방지를 위해:

- `regular_z`: 정규장 기준
- `premarket_indicative_z`: 프리마켓 참고값

으로 분리할 것.

## 7. LLM Prompt Contract

LLM 프롬프트에 아래 규칙을 고정한다.

```text
너는 Sigma를 계산하지 않는다.
입력 JSON의 값만 사용한다.
시장 전체 → 섹터 → 종목 순으로 설명한다.
숫자를 먼저 나열하지 말고 의미를 먼저 설명한다.
초보자가 이해하도록 1σ를 '이번 주 옵션시장이 가격에 반영한 예상 이동 범위'라고 풀어 쓴다.
매수/매도 추천으로 표현하지 않는다.
OI 증가를 신규 방향성 베팅이라고 확정하지 않는다.
gamma proxy를 실제 dealer positioning이라고 단정하지 않는다.
```

## 8. 브리핑 출력 설계

### 07:00 Morning

추가 섹션:

```text
📍 Sigma Market Map
- 시장 한 줄 상태
- breadth 숫자
- 가장 약한/강한 sector
- 전일 new breakout / re-entry
- 주요 confluence 3~5개
```

### 21:00 Evening

```text
🎯 오늘 밤 관전 구간
- ±1σ 경계 근접 종목
- 중요 이벤트 종목
- 전일 fast movers
```

### 22:30 Open

```text
⚡ Opening Sigma Watch
- premarket indicative z
- 정규장 기준 edge proximity
- 전일 signal과 현재 위치
```

### 05:05 Close

핵심 브리핑:

```text
📍 오늘 시장은 어디로 이동했나
🏭 어떤 섹터가 움직였나
🚨 새로 경계를 넘은 종목
↩️ 다시 범위 안으로 들어온 종목
🧭 OI/Sigma 동조 종목
```

## 9. Test Plan

### Unit Test — math

고정 fixture:

```text
anchor=100
weekly_sigma_pct=0.10
price=110 -> z=+1.0
price=90 -> z=-1.0
price=115 -> z=+1.5
```

floating tolerance 명시.

### State Test

- NORMAL -> LOWER_BREAK = new_breakout true
- LOWER_BREAK -> NORMAL = reentered true
- LOWER_BREAK 3일 = breach_age_sessions 3
- 새 주 rollover 시 breach age reset

### Breadth Test

가짜 10종목 z 배열로 mean/median/count 정확성 검증.

### Data Quality Test

- missing IV
- zero OI
- stale Yahoo candle
- CBOE 429
- symbol unavailable
- holiday Friday
- shortened session

## 10. 휴장/예외 처리

### 금요일 휴장

'마지막 실제 미국 정규장'을 anchor session으로 사용한다.

### 월요일 휴장

band는 그대로 유지. expiry까지 남은 일수는 Friday freeze 시점에 이미 확정된 값을 사용.

### 만기 이상

선택한 expiry가 예상 주간 horizon과 맞지 않으면 quality flag:

`EXPIRY_MISMATCH`

### stale data

price/option data의 session date를 반드시 저장하고, 기대 세션과 다르면:

`STALE_DATA`

으로 표시해 계산 결과를 브리핑 상위 후보에서 제외한다.

## 11. Quality Flags

각 symbol에 배열로 저장:

```json
"quality_flags": [
  "ONE_SIDED_ATM_IV",
  "STALE_DATA"
]
```

R0 후보:

- `ONE_SIDED_ATM_IV`
- `IV_MISSING`
- `EXPIRY_MISMATCH`
- `STALE_PRICE`
- `STALE_OPTIONS`
- `CBOE_RATE_LIMIT_RECOVERED`
- `INSUFFICIENT_HISTORY`

## 12. 성능/호출 비용

주간 builder가 가장 무겁다.

100종목 × CBOE 호출을 매일 하지 않는다.

- Weekly: CBOE options 전수
- Daily: Yahoo price 중심
- OI close report: 기존 필요 종목만 CBOE

장기적으로 option chain fetch cache를 공유해 같은 세션에서 중복 CBOE 호출을 제거한다.

## 13. 구현 우선순위

P0:

- timezone/state path 정리
- sigma math core
- Friday freeze

P1:

- daily z / transition
- breadth / sector
- history

P2:

- 기존 Telegram briefing 결합
- plain-language prompt

P3:

- OI confluence
- gamma concentration proxy

P4:

- dashboard/API
- historical analytics

## 14. Codex 작업 단위 권장

한 PR에 전부 넣지 않는다.

PR1 `sigma-foundation`
- timezone helper
- config
- math unit tests

PR2 `sigma-week-builder`
- CBOE parsing
- Friday freeze
- fixtures/tests

PR3 `sigma-daily-breadth`
- daily state
- transition
- market/sector breadth

PR4 `sigma-briefing-integration`
- existing reports read sigma output
- prompts/docs

PR5 `gamma-proxy`
- strike concentration
- confluence

## 15. Definition of Done — S1

S1 PASS 조건:

- deterministic 결과 재현 가능
- 최소 fixture unit tests PASS
- 같은 입력이면 같은 JSON
- Friday band가 주중 재계산되지 않음
- stale/invalid data가 조용히 정상값으로 섞이지 않음
- market/sector breadth 출력
- z transition/history 출력
- 기존 브리핑 회귀 없음
- 초보자용 한글 설명 프롬프트 연결 가능

그 다음에만 S2/Gamma 또는 웹 UI로 넘어간다.
