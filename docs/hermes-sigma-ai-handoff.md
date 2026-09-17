# Hermes Sigma Intelligence — AI / Codex Handoff

Status: SESSION HANDOFF AUTHORITY (R0)

이 문서는 새 GPT/Codex/Claude 세션이 Hermes Sigma 개발을 이어받을 때 가장 먼저 읽는 인수인계 문서다.

## 1. Repository

`zeroslove-ai/market-briefing`

목표 제품:

미국 증시/옵션 무료 데이터를 수집하고 deterministic 계산을 거쳐 한국어 Telegram briefing으로 설명하는 Hermes Market Briefing.

Sigma 확장의 목표는 **금요일에 고정한 주간 옵션 기대범위에서 현재 가격이 어디에 있는지, 시장/섹터/옵션 포지셔닝과 함께 설명하는 것**이다.

## 2. 반드시 읽을 Authority 순서

1. `docs/hermes-sigma-product-spec.md`
2. `docs/hermes-sigma-implementation-plan.md`
3. `docs/hermes-sigma-explainer.md`
4. `docs/signal-rules.md`
5. `docs/data-sources.md`
6. `docs/pitfalls.md`
7. `docs/cron-jobs.md`
8. `README.md`
9. `SKILL.md`

충돌 시 Sigma 관련 계산/구현은 1~3번 문서를 우선한다. 기존 옵션플로우 동작은 4~7번을 따른다.

## 3. 핵심 제품 원칙

### Principle A

`계산은 deterministic, 해설은 LLM.`

LLM에게 sigma 계산이나 상태 판정을 맡기지 않는다.

### Principle B

Sigma는 매매 추천 엔진이 아니다.

Sigma가 말하는 것은:

- 옵션시장이 예상한 주간 이동범위에 비해 현재 움직임이 얼마나 이례적인가
- 시장 전체/섹터/종목이 어느 방향으로 기울었는가

### Principle C

시간축을 섞지 않는다.

서로 다른 값:

- daily surprise sigma
- weekly position sigma
- 30D expected move

기존 `1SD`와 새 weekly z를 같은 값으로 취급하지 않는다.

### Principle D

Friday Freeze.

금요일(또는 마지막 실제 정규장) 이후 주간 band를 저장하고 그 주 동안 다시 계산하지 않는다.

### Principle E

가격 정본은 Yahoo regular session.

CBOE `current_price`를 가격 정본으로 사용하지 않는다.

### Principle F

공개 옵션 데이터만으로 실제 dealer 방향을 단정하지 않는다.

`dealer GEX wall` 표현 금지.

허용:

- gamma concentration
- GEX proxy
- gamma-weighted OI

## 4. S1의 정확한 범위

해야 함:

- timezone/state path 기반 정리
- universe/sector config
- ATM-IV weekly band
- Friday freeze
- daily z
- 5-state status
- delta-z
- new breakout
- re-entry
- breach age
- market breadth
- sector breadth
- previous-week history
- JSON contract
- unit tests/fixtures
- Telegram prompt가 읽을 수 있는 deterministic output

하지 않음:

- 웹 대시보드
- ML 예측
- 실시간 streaming
- 매수/매도 추천
- 복잡한 dealer-position 추정

## 5. 계산 정본

R0:

```text
weekly_sigma_pct = atm_iv * sqrt(days_to_expiry / 365)
upper_1sigma = anchor_price * (1 + weekly_sigma_pct)
lower_1sigma = anchor_price * (1 - weekly_sigma_pct)
z_score = ((current_price / anchor_price) - 1) / weekly_sigma_pct
```

상태:

```text
EXTREME_UP   z >= +1.5
UPPER_BREAK  +1.0 <= z < +1.5
NORMAL       -1.0 < z < +1.0
LOWER_BREAK  -1.5 < z <= -1.0
EXTREME_DOWN z <= -1.5
```

## 6. ATM IV R0 선택

- target expiry 선택
- anchor price와 가장 가까운 strike
- 같은 strike call/put IV 둘 다 있으면 평균
- 한쪽만 있으면 사용 가능하되 `ONE_SIDED_ATM_IV` quality flag
- 이상값/결측은 조용히 대체하지 말고 quality flag 또는 symbol skip

R0 이후 더 정교한 forward/straddle 기반 expected move는 연구 가능하지만 S1 계산 정본을 몰래 변경하지 않는다. 변경 시 method version을 올린다.

## 7. 데이터 품질이 계산보다 우선

항상 session date를 확인한다.

필수 quality flags 후보:

- ONE_SIDED_ATM_IV
- IV_MISSING
- EXPIRY_MISMATCH
- STALE_PRICE
- STALE_OPTIONS
- CBOE_RATE_LIMIT_RECOVERED
- INSUFFICIENT_HISTORY

stale/invalid 데이터는 정상 데이터처럼 briefing top candidate에 섞지 않는다.

## 8. Timezone

새 Sigma 코드에서 고정 `UTC-4` 또는 `UTC-5`를 사용하지 않는다.

```python
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
KST = ZoneInfo("Asia/Seoul")
```

미국 휴장/조기폐장 처리도 "금요일" 문자열보다 마지막 실제 정규 세션 기준으로 설계한다.

## 9. State files

권장:

```text
state/sigma_week.json
state/sigma_previous_week.json
state/sigma_daily_latest.json
state/sigma_history.jsonl
```

주의:

기존 `option_flow_report.py`는 일부 state path 사용 방식이 README 구조와 다를 수 있다. Sigma 구현 시작 시 state path를 확인하고 회귀 없이 통일한다.

## 10. 구현 순서

Codex는 아래 순서를 지킨다.

### PR1 sigma-foundation

- timezone helper
- config
- sigma pure math
- fixture tests

### PR2 sigma-week-builder

- CBOE expiry/ATM parser
- Friday freeze
- quality flags
- tests

### PR3 sigma-daily-breadth

- daily z
- transition/history
- market/sector breadth
- watchlists

### PR4 sigma-briefing-integration

- existing report JSON integration
- Telegram prompt
- beginner explanation

### PR5 gamma-proxy (S2)

- gamma concentration
- sigma-edge overlap
- confluence

한 PR에서 S1 전체를 구현하지 않는다.

## 11. 테스트 요구

작업 완료 보고 전에 최소 다음을 실제 실행한다.

### Math fixture

```text
anchor=100
weekly sigma=10%
price=110 -> z=+1.0
price=90  -> z=-1.0
price=115 -> z=+1.5
```

### Transition

- NORMAL -> BREAK
- BREAK -> NORMAL
- persistent break age
- week rollover reset

### Breadth

고정 z 배열로 mean/median/breach count 확인.

### Error

- CBOE 429
- missing IV
- stale Yahoo candle
- invalid expiry
- Friday holiday

## 12. 보고 형식

AI/Codex는 완료 시 아래만 짧게 보고한다.

```text
VERDICT: PASS / PARTIAL / BLOCKED
Branch:
HEAD:
Changed files:
Tests run:
Evidence:
Known limitations:
Next:
```

"완료했습니다"만 쓰지 않는다.

## 13. 초보자 해설 정본

브리핑에서 처음 나오는 Sigma는 가능하면 이렇게 푼다.

> 1σ는 옵션시장이 이번 주에 이 정도 범위 안에서 움직일 가능성을 가격에 반영한 예상 이동 거리입니다.

z-score는:

> 현재 가격이 그 예상 거리의 몇 배만큼 움직였는지를 나타냅니다.

예:

> -1.2σ는 하단 예상 경계를 넘어, 1σ 거리보다 약 20% 더 내려간 위치입니다.

금지:

- `-1σ = 싸다`
- `+1σ = 고평가`
- `하단 이탈 = 반등 예정`
- `상단 이탈 = 하락 예정`

## 14. LLM 해설 우선순위

항상:

1. 시장 전체
2. 섹터
3. 새로 발생한 변화
4. 주요 종목
5. OI/gamma confluence
6. 데이터 한계

종목 TOP 리스트부터 시작하지 않는다.

## 15. Reference Product

참고 UI/사고방식:

`https://sigma-dashboard-five.vercel.app/#market`

이 사이트를 그대로 복제하는 것이 목표가 아니다.

가져오는 개념:

- frozen weekly band
- common z coordinate
- market distribution
- sector distribution
- previous-week comparison
- sigma edge × gamma concentration

Hermes의 차별점:

- existing OI anomaly
- state transition / delta-z
- beginner Korean explanation
- Telegram automation
- deterministic validation/history

## 16. Next Action

새 세션이 이 문서를 읽은 뒤 첫 production 작업은 **PR1 `sigma-foundation`** 이다.

단, 시작 전 반드시 최신 `main`, open PR, existing branch를 확인한다. 이미 동일 기능이 구현되어 있으면 중복 구현하지 않는다.
