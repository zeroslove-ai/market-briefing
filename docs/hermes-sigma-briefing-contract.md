# Hermes R1 — Briefing Contract

Status: OUTPUT AUTHORITY (R1)
Parent authority: `docs/hermes-integrated-intelligence-r1.md`

이 문서는 기존 Hermes 4종 보고의 정보를 유지하면서 Sigma, OI, breadth, cross-asset, event evidence를 하나의 설명으로 합치는 규칙을 정의한다.

## 1. 공통 규칙

- 숫자 나열보다 의미를 먼저 쓴다.
- 모든 계산값은 deterministic payload를 그대로 사용한다.
- LLM은 z-score, OI 변화율, breadth, 수익률을 다시 계산하지 않는다.
- 구조는 기본적으로 **시장 -> 섹터 -> 종목 -> 다음 확인** 순서다.
- “왜”를 설명할 때 반드시 supporting evidence를 사용한다.
- 반대 근거가 있으면 숨기지 않는다.
- 원인 확인이 안 된 경우 “때문” 대신 “같은 방향”, “촉매 후보”, “시점상 연관 가능성”을 사용한다.
- Sigma는 위치/이상도이지 자동 매수·매도 신호가 아니다.
- OI 증가는 신규 방향성 포지션으로 확정하지 않는다.
- quality flag가 있는 값은 주요 결론에서 제외하거나 명시한다.

## 2. 한 보고의 3개 설명 레이어

### Layer 1 — 30초 요약

3~5문장. 전문용어 최소화.

반드시 포함할 수 있는 질문:

- 시장이 전반적으로 강했나/약했나/혼조였나?
- 어디가 움직임을 주도했나?
- 이전 보고 이후 가장 크게 달라진 것은?
- 다음에 무엇을 확인해야 하나?

### Layer 2 — 해설

핵심 움직임 2~5개를 쉬운 말로 설명한다.

예:

> NVDA가 -1.2σ라는 것은 이번 주 옵션시장이 예상한 하단 이동거리보다 약 20% 더 내려왔다는 뜻입니다. 반도체 전체도 약하고 풋 OI도 늘어, 여러 근거가 같은 방향으로 겹쳤습니다.

### Layer 3 — 근거 숫자

중요 후보에만 붙인다.

`NVDA -1.22σ | Δz -0.41 | Put OI +18% | 반도체 median -0.84σ`

Telegram에서는 표보다 한 줄 항목을 사용한다.

## 3. Evidence 표현

각 중요한 해석은 내부적으로 다음 네 가지를 가진다.

- Observation: 실제 관찰
- Support: 같은 해석을 지지하는 독립 근거
- Counter-evidence: 반대/혼재 근거
- Confidence: HIGH / MEDIUM / LOW

출력 예:

> **반도체 주도 약세 — 신뢰도 높음.** 반도체 중앙 Sigma가 -0.88σ이고 하단 이탈 비중이 41%까지 늘었습니다. SOXX도 하락했습니다. 다만 SPY 자체는 아직 -1σ 안에 있어 시장 전체 붕괴로 볼 단계는 아닙니다.

Confidence 자체를 매번 노출할 필요는 없지만, 결론이 불확실하면 문장 강도를 낮춘다.

## 4. “이전 보고 이후 무엇이 변했나”가 최우선

동일한 현재값보다 변화가 더 중요하다.

예:

> 아침 이후 분위기가 악화됐습니다. NQ 선물이 +0.6%에서 -0.1%로 뒤집혔고 VIX는 17.2에서 19.0으로 올랐습니다.

반드시 `changes_since_previous_report`가 있으면 우선 사용한다.

## 5. 07:00 아침 — Close Autopsy

기존 항목을 모두 유지한다.

1. **30초 요약**
2. **전일 미국장** — S&P/Nasdaq/NDX/Dow/Russell/SOXX
3. **Cross-asset** — 선물, VIX, 금리, DXY, 원유, 금/은, USD/KRW
4. **Sigma Market Map** — median/mean, ±1σ 이탈수, breadth bias
5. **Sector Map** — 가장 강/약한 2~3개
6. **State Changes** — new breakout/re-entry/fast mover
7. **Options/OI** — 기존 IV30/30D expected move/OI + Sigma confluence
8. **Catalyst candidates** — 실적/경제/뉴스
9. **전일 thesis 검증**
10. **다음 장 carry-over**
11. **쉽게 말하면** 1~2문장

아침 보고의 핵심 질문:

**어제 실제로 무슨 일이 일어났고, 어떤 상태가 다음 세션으로 이어지는가?**

## 6. 21:00 저녁 — Pre-market Setup

기존 지수/선물/금리/뉴스/실적/경제 내용을 유지한다.

추가 우선순위:

1. 아침 보고 이후 변화
2. 선물 방향 변화
3. 금리/VIX/DXY가 같은 방향으로 확인하는지
4. 오늘 밤 이벤트 위험
5. ±1σ 근접 종목
6. 전일 Sigma/OI 신호 현재 상태
7. 오늘 확인할 3~5개 조건

표현 예:

> 오늘 장 시작 전 핵심은 금리와 반도체입니다. 아침 이후 10년물 금리가 6bp 올라왔고 NQ 선물이 약해졌습니다. 전일 -1σ 부근이던 NVDA/AMD가 하단을 실제로 이탈하는지 확인합니다.

## 7. Opening — Opening Watch

목적은 새로운 장기 분석이 아니라 **setup 확인**이다.

- overnight/premarket/futures 변화
- regular close z와 premarket indicative z를 구분
- opening gap
- 이벤트 직후 급변
- confirm 조건
- invalidate 조건

예:

> 전일 하방 setup은 아직 확인 단계입니다. 프리마켓에서 NVDA가 -1σ 아래를 가리키지만 정규장 확정값은 아닙니다. SOXX와 NQ가 동시에 약하면 섹터 동조가 강화되고, NVDA가 빠르게 범위 안으로 돌아오면 전일 하방 이탈의 지속성은 약해집니다.

## 8. 05:05 마감 — Session Verdict

기존 옵션플로우 데이터를 유지하면서 가장 깊게 설명한다.

1. **오늘 결론**
2. **시장 내부 breadth 변화**
3. **섹터 rotation**
4. **Sigma transitions**
5. **OI anomaly / confluence**
6. **기존 conviction score + breakdown**
7. **전일/장전 관전 포인트 검증**
8. **지속 후보 / 폐기 후보**
9. **다음 세션 carry-over**

“hit/miss” 하나만으로 끝내지 않는다. 가능하면 왜 맞거나 틀렸는지 상태 변화도 같이 보여준다.

## 9. 기존 Hermes 항목 유지 규칙

기존 보고의 아래 항목은 제거하지 않는다.

- 현물 지수
- 선물
- 원유
- 달러/환율
- VIX
- 금/은
- 10Y/30Y
- Trending
- 실적
- 뉴스
- 경제 캘린더
- IV30
- 30D 1SD
- OI/OI anomaly
- legacy market_backdrop
- legacy conviction
- prior signal verification

다만 R1에서는 **데이터 섹션과 해설 섹션을 분리**해 중복을 줄인다.

## 10. Sigma 설명

첫 등장 또는 주간 첫 보고:

> 1σ는 이번 주 옵션시장이 가격에 반영한 예상 이동 거리입니다.

표현:

- +0.5σ: 상단 예상거리의 절반 이동
- -1.0σ: 하단 1σ 경계
- -1.3σ: 하단 예상거리보다 약 30% 더 이동

“과매도/고평가”처럼 자동 판단하지 않는다.

## 11. Cross-asset 설명

단일 자산으로 원인을 단정하지 않는다.

좋은 표현:

> 성장주 약세와 동시에 10년물 금리가 오르고 달러도 강해져, 금리/달러 환경이 성장주에 우호적이지 않은 모습입니다.

나쁜 표현:

> 금리가 올라서 나스닥이 떨어졌습니다.

직접적인 이벤트 근거가 없다면 인과를 낮은 강도로 표현한다.

## 12. News/Event 설명

뉴스는 “시장 설명 후보”다.

우선순위:

1. 일정이 명확한 경제지표/FOMC/실적
2. 종목에 직접 관련된 기업 발표
3. 광범위 시장 뉴스

가격 움직임 시간과 맞지 않거나 관련성이 낮으면 주요 원인으로 쓰지 않는다.

## 13. 데이터 품질

예:

> TSLA는 ATM IV가 한쪽 옵션에서만 확보돼 Sigma 위치값의 품질이 낮습니다.

> 해당 옵션체인 기준일이 최신 세션과 맞지 않아 오늘 주요 후보에서 제외했습니다.

없는 값은 추정하지 않는다.

## 14. 최종 TL;DR

최대 2문장.

좋은 예:

> → 쉽게 말하면: 지수 하락폭보다 시장 내부 약세가 더 넓어지고 있고, 특히 반도체에서 예상범위를 벗어난 종목이 늘었습니다. 오늘 밤에는 금리 상승이 이어지는지와 -1σ 이탈 종목이 범위 안으로 복귀하는지를 확인하면 됩니다.
