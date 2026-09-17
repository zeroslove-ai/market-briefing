# Hermes Sigma — Reference Notes / Design Decisions

## Reference

Primary visual/product reference:

`https://sigma-dashboard-five.vercel.app/#market`

Hermes는 해당 제품을 복제하지 않는다. 참고하는 것은 다음 구조다.

- weekly frozen sigma band
- common z-score coordinate
- market breadth / distribution
- sector breadth
- previous week comparison
- sigma edge와 gamma concentration의 결합

## Hermes가 추가하는 차별점

1. 기존 무료 OI anomaly와 결합
2. `delta_z`, breakout/re-entry, breach age 등 상태 전이
3. 한국어 비전문가 해설
4. Telegram 자동 브리핑
5. 계산/해설 분리
6. quality flag와 stale-data 방어
7. 이후 history 기반 검증

## Decision Log

### D1 — Weekly band는 Friday Freeze

채택.

이유: 주중 IV가 변할 때 매일 band 자체가 움직이면 "가격이 움직인 것"과 "기준자가 움직인 것"을 구분하기 어렵다.

### D2 — R0 weekly expected move는 ATM IV formula

채택.

```text
atm_iv * sqrt(days_to_expiry / 365)
```

이유: 현재 무료 CBOE data로 재현 가능하고 계산이 투명하다.

향후 straddle-implied expected move와 비교해 calibration 가능.

### D3 — 기존 30D 1SD 제거 안 함

채택.

기존 기능은 보존하되 명칭과 시간축을 분리한다.

### D4 — Daily Sigma와 Weekly Sigma 분리

채택.

하루 surprise와 주간 position을 같은 값으로 쓰지 않는다.

### D5 — Gamma는 proxy만

채택.

공개 체인으로 dealer long/short 방향을 확정할 수 없으므로 `gamma concentration`만 말한다.

### D6 — 웹 UI는 S1 이후

채택.

먼저 JSON intelligence layer와 Telegram briefing을 안정화한다.

### D7 — 초보자 설명을 product requirement로 포함

채택.

단순 도움말이 아니라 briefing contract에 포함한다.

## Open Research Questions

S1 구현 뒤 실제 history로 조사:

1. ATM IV 방식과 ATM straddle 방식 중 실제 다음 주 realized range calibration이 더 나은가?
2. calendar days vs trading days convention 차이는 얼마나 큰가?
3. ±1.0 / ±1.5 threshold를 그대로 유지할지?
4. `fast_mover abs(delta_z)>=0.30`의 적정 threshold는?
5. sector breach ratio가 시장 설명력에 얼마나 기여하는가?
6. OI 변화와 sigma breakout의 합치가 다음 세션 follow-through와 관계가 있는가?
7. gamma concentration edge overlap이 실제 intraday reaction과 관계가 있는가?

이 질문은 production S1을 막지 않는다. history 축적 후 검증한다.
