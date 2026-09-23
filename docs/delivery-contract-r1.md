# Hermes R1 — Dual Delivery Contract (Email Newsletter + Telegram Compact)

Status: OUTPUT / DELIVERY AUTHORITY
Parent:
- `docs/hermes-integrated-intelligence-r1.md`
- `docs/hermes-sigma-briefing-contract.md`
- `docs/hermes-korean-explanation-r1.md`

## 1. 원칙

같은 canonical JSON에서 **두 개의 별도 결과물**을 만든다.

1. **Email Newsletter — Full**
   - 읽고 공부하는 버전
   - 시장/거시/뉴스/실적/Sigma/OI를 충분히 설명
   - source link 포함
   - 중급자 설명 + 필요 시 초보자 보조 해설
   - 5~10분 읽기

2. **Telegram — Compact**
   - 2~3분 내 확인
   - 가장 중요한 변화/일정/리스크만
   - 표 금지, 한 줄 항목
   - 긴 뉴스 설명/교육 문단은 이메일로 넘김

두 결과는 서로 다른 계산을 하지 않는다.
동일 snapshot / 동일 evidence를 길이와 설명 깊이만 달리해 렌더링한다.

---

## 2. 06:30 Morning 기준

Morning snapshot cutoff:

- 기준 시각: **06:30 KST**
- 미국 정규장 close 이후 확정된 가격/뉴스/실적을 포함
- 06:30 이후 나온 정보는 다음 report 또는 breaking update로 이월
- artifact에 `cutoff_at_kst` 저장

예:
`2026-09-23T06:30:00+09:00`

---

## 3. 시간 표기 규칙 — 매우 중요

사용자-facing 모든 시간은 **KST 우선**.

좋음:
`22:45 KST — S&P Global 미국 Flash PMI (09:45 ET)`

나쁨:
`09:45 ET — Flash PMI`

날짜가 넘어가면 반드시 표시:

`00:00 KST (9/24) — Atlanta Fed Business Inflation Expectations`

경제 캘린더와 실적 발표는 KST 날짜/시간으로 정렬한다.

---

## 4. 경제 캘린더 계약

Email에는 그날 미국시장에 관련된 **모든 추적 이벤트**를 시간순으로 싣는다.

각 row/항목 필수:
- KST 날짜/시간
- 이벤트명
- 중요도
- 이전
- 예상
- 실제 (발표 후 report이면)
- 한 줄 의미
- source

예:

```text
20:00 KST | MBA 모기지 신청 | 낮음 | 이전 -4.1%
22:45 KST | S&P Global 제조업 PMI | 높음 | 예상 53.5 / 이전 53.9
22:45 KST | S&P Global 서비스 PMI | 높음 | 예상 56.0 / 이전 56.5
23:05 KST | Fed Barr 이사 연설: Housing | 중간
23:30 KST | EIA 원유재고 | 중간 | 이전 -0.64M
02:00 KST (9/24) | 미 5년물 국채 입찰 | 중간
```

Telegram:
- HIGH/MEDIUM 위주
- LOW라도 원유/금리 등 시장 상황상 relevant하면 포함
- 최대 5~7줄
- “전체 일정은 이메일” 링크/문구 가능

---

## 5. 실적 캘린더 계약

시간은 세 종류를 구분한다.

### A. 회사가 공식 발표 시각을 공지
정확한 KST 표기.

### B. 회사가 Before Open / After Close만 공지
`장전 (21:30 KST 이전)`, `장후 (05:00 KST 이후)`로 표기.
calendar provider의 추정 시각을 official time처럼 쓰지 않는다.

### C. Conference call
실적 발표와 별도 필드로 표기.

각 주요 기업 필수:
- ticker / 회사명
- 발표 window 또는 공식 발표 시각
- conference call 시각
- 예상 EPS
- 예상 매출 (확보 가능할 때)
- 시총/중요도
- 현재 price/Sigma/IV context (engine 구현 후)
- “무엇을 볼 것인가”

예:

```text
PAYX Paychex
- 실적: 장전 / calendar estimate 21:30 KST
- 공식 conference call: 22:30 KST
- EPS 예상: $1.32
- 체크: Paycor 통합 효과, client retention, FY guidance

CTAS Cintas
- 실적: 장전 (공식 날짜 확인; 정확한 공시 시각 미고정)
- 공식 conference call: 23:00 KST
- EPS 예상: 약 $1.35~1.36
- 체크: organic growth, margin, FY guidance, UniFirst deal/regulatory commentary
```

---

## 6. Email Newsletter 구성

Subject 예:
`[미국증시 모닝] AI 강세 vs 시장 확산도 둔화 | 9/23 06:30 KST`

본문:

### 0. 30초 요약
4~6줄.

### 1. Overnight Market
- S&P / Nasdaq / Dow / Russell / SOXX
- futures if relevant
- VIX / 10Y / DXY / Oil / Gold
- “왜 중요” 해설

### 2. Market Internals
- breadth
- sector rotation
- Weekly Sigma
- breakout/re-entry
- relative strength

### 3. Top Stories
3~7개 story cluster.
각 story:
- 핵심
- 왜 중요
- 시장 반응
- 다음 체크
- source link

### 4. Corporate / SEC / Earnings Review
전일 실적/공시와 price reaction.

### 5. 오늘 경제 캘린더 — KST
**추적 대상 전체** 시간순.

### 6. 오늘 주요 실적 — KST
주요 회사 + 예상 + 관전 포인트.

### 7. Options / Sigma Watch
- IV30
- OI anomalies
- weekly edges
- confluence

### 8. 오늘 밤 3~5개 체크포인트

### 9. 초보자 보조 해설
필요한 날에만 2~4개 개념 설명.
예: bp, PMI, IV, Sigma.

### 10. Sources
공식 source 우선.

---

## 7. Telegram Compact 구성

목표: 스크롤 1~2화면, 최대 약 1,500~2,500자 권장.

```text
☀️ 미국증시 모닝 | 9/23 06:30 KST

한줄:
AI/나스닥은 강했지만 S&P 보합·다우 약세로 상승 폭은 좁았습니다.

📈 시장
S&P ... | Nasdaq ... | SOXX ...
10Y ... | VIX ... | WTI ...

🧭 핵심 해석
• ...
• ...
• ...

📰 뉴스 TOP3
• META ...
• 유가 ...
• Fed ...

🗓 오늘 일정 (KST)
20:00 MBA 모기지
22:45 美 Flash PMI ★★★
23:05 Fed Barr 연설 ★★
23:30 EIA 원유재고 ★★
02:00(9/24) 美 5Y 입찰 ★★

🏢 주요 실적
20:00대 GIS 장전 | EPS $0.72
21:30대 PAYX 장전 | EPS $1.32 | Call 22:30
CTAS 장전 | EPS ~$1.35 | Call 23:00

🎯 오늘 체크
1) ...
2) ...
3) ...

상세 뉴스·해설·전체 캘린더 → 이메일 뉴스레터
```

뉴스 full summary, 긴 교육 설명, low-priority calendar는 Telegram에서 제외한다.

---

## 8. Breaking Update

Morning 이후 CRITICAL event 발생 시 전체 newsletter 재발행 금지.

Telegram:
`🚨 Breaking Update`

Email:
- 정말 큰 사건만 별도 short email
- 아니면 21:00 newsletter에 반영

---

## 9. Delivery pipeline

```text
canonical JSON
   ├─ render_email_full()
   │     └─ Gmail / SMTP delivery
   └─ render_telegram_compact()
         └─ Telegram delivery
```

두 renderer는 별도 LLM call을 사용할 수 있으나:
- same input
- same evidence
- no recalculation
- same cutoff

를 강제한다.

---

## 10. Email technical recommendation

우선순위:

1. Gmail API/connected Gmail
2. SMTP fallback

email artifact:
- plain text + HTML multipart
- 모바일 우선
- wide table 최소화
- source link clickable
- section headings
- 06:30 cutoff 명시

Subject에 핵심 regime 변화 1개만 넣는다.

---

## 11. Telegram technical recommendation

- Telegram Bot API
- 현재 topic delivery 유지
- Markdown table 금지
- section spacing
- compact source link는 TOP story에만
- 메시지가 너무 길면 2개 message까지 허용:
  1) market/news
  2) calendar/earnings/watch

기본은 1 message를 목표.

---

## 12. 완료 기준

- 경제 일정은 KST 시간순이며 날짜 rollover가 명확함
- 주요 실적은 발표 window와 conference call을 구분
- Email은 full analysis
- Telegram은 compact
- 두 채널의 핵심 결론/숫자가 서로 충돌하지 않음
- Morning cutoff가 06:30 KST로 고정/기록됨
