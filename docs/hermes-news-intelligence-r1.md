# Hermes R1 — News & Event Intelligence Authority

Status: DESIGN AUTHORITY
Parent: `docs/hermes-integrated-intelligence-r1.md`
Target reader: **주식 중급자** — 지수/금리/PER/실적/옵션의 기본 개념은 알지만, 매일 여러 소스를 직접 연결해 해석하기는 부담스러운 사용자

## 1. 목표

Hermes의 뉴스 기능은 “헤드라인 5개 번역”이 아니라 다음 질문에 답해야 한다.

1. 오늘 시장에 **실제로 중요한 뉴스가 무엇인가?**
2. 그 뉴스는 **어떤 종목/섹터/자산에 연결되는가?**
3. 뉴스가 나온 뒤 **가격과 시장 내부가 실제로 반응했는가?**
4. 같은 이야기가 여러 기사로 반복되는 것인가, **새 정보가 추가된 것인가?**
5. 투자자가 다음 세션에서 **무엇을 확인해야 하는가?**

뉴스는 가격 움직임의 “원인”으로 자동 확정하지 않는다. 뉴스/이벤트 시점과 가격·Sigma·OI·sector reaction이 함께 확인될 때만 강한 설명을 허용한다.

## 2. 소스 계층

### Tier A — 1차 공식 소스 (가장 높은 authority)

#### SEC EDGAR
목적:
- 8-K
- 10-Q / 10-K
- 6-K / 20-F
- S-3 / 424B 등 증자·자금조달 관련
- Form 4는 R1 core 밖이지만 향후 확장 가능

수집:
- SEC company ticker -> CIK mapping
- `data.sec.gov/submissions/CIK##########.json`
- 최근 filing accession/form/filingDate/reportDate/primaryDocument

활용:
- “기업이 실제로 공시한 사실”의 최우선 정본
- 언론 기사보다 원문 우선
- 8-K가 earnings release를 포함하면 company event로 연결

주의:
- filing form 자체만으로 내용/방향을 추론하지 않는다.
- materiality는 form + item/exhibit + watchlist relevance로 판단.

#### Federal Reserve
목적:
- FOMC statement / projections / minutes
- press releases
- speeches/testimony
- policy/financial stability 관련 공지

활용:
- CNBC 기사보다 Fed 원문을 macro event 정본으로 사용
- 연설은 제목만이 아니라 본문 핵심 문장을 LLM이 요약하되, deterministic metadata와 분리

#### BLS
목적:
- CPI
- PPI
- Employment Situation
- unemployment
- payroll
- wages
- job openings 등

수집:
- BLS public API
- release calendar/event metadata는 별도 source adapter

#### BEA
목적:
- GDP
- PCE / Personal Income and Outlays
- trade
- corporate profits

활용:
- release schedule + release result
- forecast는 별도 economic calendar와 결합

### Tier B — 시장 뉴스/설명 소스

#### CNBC RSS — 기존 유지
역할:
- 시장 전체 헤드라인
- 기업 뉴스
- 당일 화제
- 설명/맥락 보강

원칙:
- Tier A 원문이 있는 사건은 Tier A를 canonical source로 삼고 CNBC는 context source로 둔다.
- 동일 사건 기사 여러 개는 cluster로 묶는다.

### Tier C — Discovery

- Yahoo Trending
- 향후 추가 가능한 공개 RSS/커뮤니티 source

역할:
- “무엇이 화제인가” 탐색
- fact authority로는 사용하지 않음
- Tier A/B로 사실을 확인할 수 있으면 승격

## 3. News Event Object

모든 뉴스/공시/경제이벤트를 공통 구조로 normalize한다.

```json
{
  "event_id": "2026-09-23_NVDA_8K_xxx",
  "published_at": "...",
  "source_tier": "A",
  "source": "SEC",
  "source_url": "...",
  "event_type": "EARNINGS|GUIDANCE|FILING|FED|MACRO_DATA|MNA|CAPITAL|PRODUCT|LEGAL|REGULATION|GEOPOLITICAL|SECTOR",
  "entities": ["NVDA"],
  "sectors": ["Semiconductors"],
  "headline": "...",
  "facts": [],
  "summary_ko": "...",
  "novelty": "NEW|UPDATE|DUPLICATE",
  "materiality": "CRITICAL|HIGH|NORMAL|LOW",
  "market_scope": "MARKET|SECTOR|COMPANY",
  "related_assets": ["SOXX", "NQ=F"],
  "price_reaction": {},
  "sigma_context": {},
  "oi_context": {},
  "confidence": "HIGH|MEDIUM|LOW",
  "quality_flags": []
}
```

LLM이 headline에서 ticker를 임의 추측하는 것이 아니라 entity linker가 먼저 mapping한다.

## 4. Event taxonomy

### Macro
- FOMC / Fed speech
- CPI/PPI/PCE
- payroll/unemployment/wages
- GDP
- ISM/PMI (source 확보 후)
- Treasury/rates related event
- FX/liquidity

### Company
- earnings
- guidance raise/cut
- revenue/EPS surprise
- M&A
- buyback/dividend
- capital raise/debt
- management change
- product/AI capex
- major contract
- legal/regulatory
- SEC filing

### Sector
- semiconductor export controls
- cloud/AI capex cycle
- bank regulation
- oil/OPEC/geopolitics
- healthcare regulation
- consumer demand

## 5. Dedup / Story Clustering

동일 사건을 뉴스 5건으로 보여주지 않는다.

cluster key 후보:
- normalized entities
- event_type
- 6~12h time window
- headline token similarity

대표 source 선택:
1. official Tier A
2. trusted Tier B
3. discovery Tier C

cluster 출력:
- canonical headline
- primary source
- supporting sources
- update_count
- latest_update
- new_fact 여부

예:
“NVDA earnings” 관련 CNBC 3개 + SEC 8-K 1개가 있으면 하나의 cluster로 출력한다.

## 6. Materiality

가짜 정밀 숫자 하나로 만들지 않고 등급 + 근거를 저장한다.

### CRITICAL
- FOMC/CPI/jobs처럼 시장 전체 영향
- watch universe 대형주의 earnings/guidance
- M&A/대규모 capital event
- price move와 직접 연결될 가능성이 높은 공식 공시

### HIGH
- 섹터 전체 영향 규제/정책
- 주요 Fed 발언
- watchlist 기업의 material 8-K
- 실적 발표 전후 핵심 update

### NORMAL
- 일반 기업 뉴스
- 반복되는 시장 코멘트
- 영향 범위 제한적

### LOW
- 중복 기사
- 근거 약한 전망성 기사
- watch universe와 연결 없음

materiality reason 예:
`official filing + mega-cap + earnings + abnormal price reaction`

## 7. Price Reaction Linking

뉴스를 읽고 “주가가 올랐다”를 임의 연결하지 않는다.

R1 close 기준 가능한 최소 연결:

- ticker regular return
- sector ETF return
- market return
- relative return = ticker - sector/market
- weekly sigma z / delta-z
- new breakout/re-entry
- OI anomaly

예:

```text
MSFT +4.1%
XLK +0.8%
relative +3.3%p
weekly z: +0.5 -> +1.2
call OI anomaly: none
```

해설:
“실적/가이던스 발표와 같은 세션에 MSFT가 섹터 대비 3.3%p 강했고 +1σ를 넘어섰습니다. 가격 반응은 뚜렷하지만 OI 동조는 확인되지 않았습니다.”

이것은 “뉴스가 상승을 만들었다”가 아니라 **event + reaction alignment**다.

## 8. News Relevance to intermediate investor

중급자에게는 기사 요약보다 아래가 더 중요하다.

각 핵심 뉴스에 최대 4줄:

1. **무슨 내용?**
2. **왜 주가에 중요?**
3. **실제 시장 반응?**
4. **다음 확인 포인트?**

예:

```text
[NVDA] 신규 수출 제한 관련 공식 발표
- 핵심: 특정 지역 AI GPU 판매 조건이 강화됨.
- 왜 중요: NVDA 매출 성장 기대와 데이터센터 공급 경로에 직접 연결.
- 반응: NVDA -2.8%, SOXX -1.1%, NVDA -0.9σ -> -1.3σ.
- 체크: 하단 이탈이 다음 세션에도 유지되는지와 put OI 동조 여부.
```

## 9. Macro explanation standard

단순 “10년물 4.3%” 대신 관계를 설명한다.

### Rates
“10년물 +8bp”:
- 장기 할인율 압력이 상승
- 특히 고밸류/장기 성장 기대에 민감한 종목에 부담 가능
- 단, 같은 날 성장주가 강하면 counter-evidence

### VIX
절대 수준 + 변화 둘 다 본다.
- 15 -> 19: 아직 극단 공포는 아니지만 위험 프리미엄이 빠르게 확대
- 24 -> 19: 여전히 높지만 stress는 완화

### DXY
- 달러 강세는 글로벌 risk appetite/미국 다국적 기업 환산 실적에 부담 가능
- 단순 인과 단정 금지

### Oil
- energy에는 직접적
- headline inflation expectation / consumer cost에는 간접적
- 단기 하루 움직임으로 CPI 방향 단정 금지

### Yield curve / 2Y
R1에서 안정된 공식/무료 source를 붙이면 추가.
현재 Yahoo 2Y 제약이 있으므로 별도 검증 전 report 필수값으로 만들지 않는다.

## 10. Earnings Intelligence

R1 최소:

### Before
- 발표 시간
- EPS forecast
- market cap / importance
- current sigma position
- IV30 / 30D expected move
- weekly edge distance
- prior 5-session move

### After
- actual vs expected — source 확보 시
- guidance direction
- price reaction
- sector-relative reaction
- sigma transition
- OI change
- filing/news canonical source

출력:

```text
AMD 실적 예정
예상 EPS $x.xx | 현재 +0.72σ | IV30 xx%
옵션시장은 평소보다 큰 변동을 가격에 반영하고 있으며 상단 1σ까지 거리가 짧음.
실적 후 실제 방향은 숫자보다 guidance와 데이터센터 매출 반응을 우선 확인.
```

R1에서 analyst target/consensus estimate를 무료/안정 source 없이 창작하지 않는다.

## 11. Daily News Digest by report phase

### 07:00 — What moved the market
- overnight/US-session top 3~5 stories
- official macro releases
- earnings/8-K
- story + price reaction
- “뉴스 없이 움직인” 주요 Sigma/OI event도 별도 표시

### 21:00 — What changed since morning
- morning 이후 new stories only
- tonight macro calendar
- tonight earnings
- Fed speeches/events
- watchlist/company filings
- duplicate morning story 반복 금지

### Opening
- 21:00 이후 breaking/update
- futures/premarket reaction
- event confirm/invalidate
- 매우 짧게

### 05:05 — Session catalyst review
- 세션 중 핵심 뉴스
- 뉴스 cluster별 실제 price/sector/Sigma/OI reaction
- headline과 price가 불일치한 경우 명시
- next-session unresolved story

## 12. “News without noise” rule

기본 Telegram에서 모든 기사를 보여주지 않는다.

- CRITICAL: 모두
- HIGH: 최대 5
- NORMAL: 의미 있는 update만
- LOW/DUPLICATE: 보관만 하고 기본 보고 생략

단, “오늘 수집한 뉴스 N건 / cluster M개 / 최종 중요뉴스 K개”는 metadata로 남긴다.

## 13. Source / evidence separation

각 문장은 다음 중 하나다.

- FACT: source 원문
- MARKET OBSERVATION: deterministic price/data
- INTERPRETATION: evidence engine
- WATCH: future confirmation condition

예:

```text
FACT: Fed가 ... 발표했다.
OBSERVATION: 발표 이후 세션에서 10Y +8bp, NQ -1.1%.
INTERPRETATION: 금리와 성장주가 같은 방향으로 반응해 긴축적 해석과 정합적.
WATCH: 다음 세션에도 10Y 상승과 NQ 약세가 유지되는지 확인.
```

이 구조를 payload에도 저장한다.

## 14. Suggested code modules

```text
scripts/
  news_collect.py
  news_normalize.py
  news_cluster.py
  news_entities.py
  news_reaction.py
  sec_events.py
  fed_events.py
  macro_official.py

state/news/
  raw/YYYY-MM-DD.jsonl
  clusters/YYYY-MM-DD.json
  latest.json
  seen_ids.json

config/
  news_sources.json
  event_taxonomy.json
  ticker_cik.json
```

## 15. Implementation order

### N1 — Preserve existing
- CNBC RSS adapter
- Nasdaq earnings
- investing.com calendar
- normalize to event object

### N2 — Official sources
- SEC ticker/CIK mapping
- SEC recent filings
- Fed RSS/page adapters
- BLS public API
- BEA release schedule/result adapter

### N3 — Intelligence
- entity linking
- dedup/story clustering
- materiality
- novelty
- market/sector relationship

### N4 — Reaction
- price/sector relative
- Sigma
- OI

### N5 — Four-report integration
- phase-aware delta
- no duplicate stories
- source attribution
- intermediate investor explanation

## 16. Definition of Done

News Intelligence PASS:

- 기존 CNBC 뉴스 기능이 사라지지 않는다.
- SEC/Fed/BLS/BEA 공식 source가 별도 source tier로 들어온다.
- 같은 사건 중복 기사가 cluster된다.
- 각 핵심 story에 affected asset/entity가 연결된다.
- “왜 중요한지”가 중급 투자자 수준으로 설명된다.
- 가격/Sigma/OI 반응이 있으면 함께 표시한다.
- 근거 없는 인과관계를 만들지 않는다.
- 오전에 본 뉴스가 업데이트 없이는 저녁에 그대로 반복되지 않는다.
- source URL / timestamp / source tier가 저장된다.
