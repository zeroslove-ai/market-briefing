# Hermes R1 — Implementation Plan

Status: IMPLEMENTATION AUTHORITY (R1)
Parent: `docs/hermes-integrated-intelligence-r1.md`

이 문서는 기존 Hermes 4종 보고를 유지하면서 Sigma와 Evidence Engine을 안전하게 production에 넣는 구현 순서를 정의한다.

## 1. 구현 원칙

- 기존 브리핑 기능을 삭제하지 않는다.
- 동일 데이터는 한 번 수집하고 공통 snapshot에서 재사용한다.
- 가격 정본은 Yahoo regular session.
- CBOE는 IV/OI/Greeks 전용.
- 계산은 deterministic, LLM은 설명 전용.
- 모든 상태 파일은 repo-root `state/`.
- session date와 quality flag를 저장한다.
- DST offset 숫자를 하드코딩하지 않는다.
- 기존 30D expected move와 Weekly Sigma를 혼용하지 않는다.
- 새 기능은 단계별 PR로 넣고 기존 4 reports regression을 매 단계 확인한다.

## 2. Target 구조

```text
scripts/
  market_data.py
  market_clock.py
  market_state.py
  evidence_engine.py
  briefing_payload.py
  sigma_shared.py
  sigma_build_week.py
  sigma_daily.py
  option_flow_report.py
  us_market_report.py

config/
  universe.json
  sector_map.json
  thresholds.json

state/
  market_snapshot_latest.json
  report_snapshots/
  report_history/
  option/
    oi_close_snapshot.json
    flow_signals.json
  sigma/
    week.json
    previous_week.json
    daily_latest.json
    history.jsonl

tests/
  fixtures/
  test_market_clock.py
  test_state_paths.py
  test_data_authority.py
  test_sigma_math.py
  test_sigma_state.py
  test_breadth.py
  test_evidence.py
  test_report_delta.py
  test_legacy_regression.py
```

파일명은 구현 중 조정 가능하지만 **소유권 분리**는 유지한다.

## 3. PR0 — `hermes-data-core`

Sigma보다 먼저 진행한다.

### 3.1 market_clock

`ZoneInfo("America/New_York")`와 `ZoneInfo("Asia/Seoul")`을 사용한다.

출력 예:

```json
{
  "now_et": "...",
  "now_kst": "...",
  "market_session_date": "2026-09-18",
  "phase": "close",
  "last_regular_session": "2026-09-18"
}
```

정규장 날짜는 단순 UTC 날짜가 아니라 ET 기준으로 저장한다.

### 3.2 state paths

현재 일부 스크립트가 script directory에 snapshot을 쓴다. 모두 repo root `state/`로 통일한다.

모든 persistent JSON에:

- schema_version
- generated_at
- session_date
- source

를 넣는다.

### 3.3 price authority

`us_market_report.py` 옵션 섹션의 CBOE `current_price`와 `price_change_percent` 사용을 제거한다.

- price/change: Yahoo
- IV/OI/Greeks: CBOE

### 3.4 OI baseline ownership

현재 아침/저녁 `us_market_report.py`가 실행될 때마다 OI snapshot을 갱신할 수 있다.

R1:

- close session에서만 baseline commit
- morning/evening/open은 read-only
- baseline에 `session_date` 저장
- 같은 session_date 재실행은 overwrite 가능하되 ‘전일’ 기준은 바뀌지 않음
- 새 session이 확정될 때 이전 baseline과 diff

### 3.5 per-run cache

같은 run에서 동일 Yahoo/CBOE URL을 여러 번 호출하지 않는다.

CBOE는 특히 cache + 순차/backoff를 사용한다.

### 3.6 earnings target session

`date.today()` 대신 `market_session_date` 또는 `next_us_session_date`를 사용한다.

07:00 KST와 21:00 KST에서 “오늘 실적”이 어떤 미국 세션을 의미하는지 명확해야 한다.

### PR0 PASS

- 기존 4 reports가 기존 필드를 계속 출력
- CBOE 가격이 보고 가격으로 사용되지 않음
- OI baseline이 하루 여러 보고에 의해 오염되지 않음
- state path 일관
- ET/KST session label 정확
- duplicate fetch 감소

## 4. PR1 — `sigma-foundation`

### 4.1 Config

- `config/universe.json`
- `config/sector_map.json`
- `config/thresholds.json`

### 4.2 Pure math

```text
weekly_sigma_pct = atm_iv * sqrt(days_to_expiry / 365)
upper = anchor * (1 + weekly_sigma_pct)
lower = anchor * (1 - weekly_sigma_pct)
z = ((price / anchor) - 1) / weekly_sigma_pct
```

fixture:

- anchor 100
- sigma 10%
- 110 => +1
- 90 => -1
- 115 => +1.5

### 4.3 state classification

- EXTREME_UP
- UPPER_BREAK
- NORMAL
- LOWER_BREAK
- EXTREME_DOWN
- near edge

## 5. PR2 — `sigma-week-builder`

### expiry selection

R1 initial policy:

1. last actual regular session close를 anchor
2. 목표는 다음 주 horizon에 맞는 가장 가까운 유효 expiry
3. expiry/date mismatch는 quality flag

### ATM IV

1. anchor price와 가장 가까운 strike
2. 같은 strike call/put IV 둘 다 있으면 평균
3. 한쪽만 있으면 사용 + `ONE_SIDED_ATM_IV`
4. invalid IV는 제외

### output

`state/sigma/week.json`

주중에는 freeze 값을 변경하지 않는다.

## 6. PR3 — `sigma-daily-breadth`

### per-symbol

- z
- prev_z
- delta_z
- status
- edge distance
- new breakout
- re-entry
- breach age
- max abs z

### market

- mean/median
- ±1 counts
- ±1.5 counts
- near-edge
- breadth bias

### sector

- count
- mean/median
- up/down breach
- breach ratio
- delta median z

### watchlists

- new breakout
- re-entry
- fast mover
- persistent break
- extreme
- near edge

## 7. PR4 — `report-snapshot-delta`

각 브리핑 실행 결과를 저장한다.

```text
latest_morning
latest_evening
latest_open
latest_close
history
```

현재 payload와 이전 관련 payload를 비교해:

```json
{
  "changes_since_previous_report": {
    "NQ_change_pct_delta": -0.7,
    "VIX_delta": 1.8,
    "TNX_bp_delta": 6,
    "sigma_lower_break_count_delta": 5
  }
}
```

필드 이름은 구현에서 구조화하되 “이전 보고 이후 변화”가 반드시 machine-generated여야 한다.

## 8. PR5 — `evidence-engine`

### 입력

- normalized market snapshot
- Sigma
- OI/options
- events/news
- previous-report deltas

### 출력

```json
{
  "claim_id": "...",
  "observation": "...",
  "support": [],
  "counter_evidence": [],
  "confidence": "HIGH|MEDIUM|LOW",
  "quality_flags": []
}
```

### confidence

HIGH:
- 3개 이상 독립 축 동조
- 주요 반대근거 없음

MEDIUM:
- 2개 축 동조
- 또는 3개 이상이지만 반대근거 있음

LOW:
- 단일 축
- 또는 quality 제한

같은 데이터 원천에서 파생된 숫자를 독립축으로 중복 계산하지 않는다.

### initial claims

- BREADTH_DOWN/UP
- SECTOR_LED_WEAKNESS/STRENGTH
- RISK_OFF/RISK_ON_CONFIRMED
- CROSS_ASSET_MIXED
- RATES_HEADWIND_GROWTH
- VOLATILITY_EXPANSION
- IDIOSYNCRATIC_MOVE
- SIGMA_OI_CONFIRMED
- SIGMA_OI_CONFLICT
- EVENT_RISK_DOMINANT
- REENTRY_AFTER_EXTREME

## 9. PR6 — `four-report-integration`

공통 `briefing_payload.py`가 phase별 payload를 만든다.

### Morning

- legacy data
- prior close autopsy
- Sigma map
- sector
- OI
- catalyst candidates
- carry-over

### Evening

- morning 이후 delta
- futures/rates/VIX/USD
- event risk
- sigma edge watch
- prior signals

### Open

- evening 이후 delta
- indicative gap
- regular vs indicative sigma
- confirm/invalidate

### Close

- open 이후 delta
- breadth
- sector rotation
- sigma transitions
- fresh OI
- prior thesis outcome
- carry-over

기존 script entrypoint는 필요하면 wrapper로 유지해 cron 설정을 한번에 깨지 않는다.

## 10. PR7 — `explanation-qa`

LLM contract test용 고정 fixture를 만든다.

검사:

- payload에 없는 숫자를 출력하지 않음
- Sigma 재계산하지 않음
- OI를 신규 베팅 확정으로 말하지 않음
- 뉴스가 없는데 원인을 창작하지 않음
- counter-evidence가 있으면 일방적 확신 표현을 피함
- 첫 Sigma 설명이 비전문가에게 이해 가능
- 모바일 Telegram에서 wide table 없음

## 11. Legacy score 정책

기존:

- market_backdrop
- conviction score

는 삭제하지 않는다.

R1에서는:

- `legacy.market_backdrop`
- `legacy.conviction`

으로 보존 가능하며, 외부 보고에서는 필요할 때 표시한다.

새 Evidence Engine은 이 점수를 그대로 “진실”로 취급하지 않는다.

## 12. Scheduler / DST

우선순위:

1. scheduler가 timezone 지원 -> America/New_York 사용
2. 미지원 -> EDT/EST 두 KST 후보 시간에 wrapper 실행
3. wrapper가 ET phase + session data를 검사
4. 같은 session/phase는 no-op

이 방식으로 매년 3월/11월 수동 cron 수정 의존을 제거한다.

## 13. Data Quality

공통 flag 후보:

- STALE_PRICE
- STALE_OPTIONS
- IV_MISSING
- ONE_SIDED_ATM_IV
- EXPIRY_MISMATCH
- RATE_LIMIT_RECOVERED
- INSUFFICIENT_HISTORY
- SESSION_DATE_MISMATCH
- FALLBACK_SOURCE

중요 결론은 invalid/stale 값을 제외한다.

## 14. Historical outcome tracking

기존 next-close hit/miss는 유지하되 확장한다.

각 signal/event:

- +1 session return
- +3 session return
- +5 session return
- max favorable excursion
- max adverse excursion
- sigma re-entry time
- signal class

초기에는 예측 확률을 만들지 않는다. 표본이 쌓인 뒤 threshold review에만 사용한다.

## 15. PR 순서

1. PR0 `hermes-data-core`
2. PR1 `sigma-foundation`
3. PR2 `sigma-week-builder`
4. PR3 `sigma-daily-breadth`
5. PR4 `report-snapshot-delta`
6. PR5 `evidence-engine`
7. PR6 `four-report-integration`
8. PR7 `explanation-qa`
9. S2 `gamma-proxy`

## 16. Definition of Done

R1 PASS:

- 기존 4 reports 정보 보존
- common data authority
- session/date correctness
- OI baseline correctness
- Friday frozen Sigma
- daily/sector breadth
- report-to-report delta
- evidence + counter-evidence
- phase-specific briefing
- beginner/expert layered explanation
- deterministic fixtures
- legacy regression PASS
- unsupported causal claims 없음
