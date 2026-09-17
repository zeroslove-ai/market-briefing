---
name: market-data-collection
description: "미국 주식/시장 데이터 무료 수집: Yahoo/Nasdaq/CNBC API 실측 검증, 크론 보고 구성."
version: 1.0.0
author: Hermes Agent (curator)
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [stocks, market-data, yahoo-finance, nasdaq, rss, cron, report]
---

# 미국 주식/시장 데이터 수집 (무료 소스)

Use when the user wants US stock quotes, indices, index futures, trending
tickers, earnings calendars, or a scheduled market briefing (아침/저녁 보고).
All sources below were **live-verified Aug 2026** — symbol tables and limits
are measured, not guessed.

## 검증된 무료 소스 (2026-08 실측)

| 용도 | 소스 | 키 | 실측 결과 |
|---|---|---|---|
| 지수/선물/종목 시세 | **Yahoo chart API** | 불필요 | ✅ 지수·선물·ETF 모두 동작 |
| 화제 종목 | Yahoo Trending | 불필요 | ✅ 20개 반환 |
| 실적 발표 캘린더 | **Nasdaq API** | 불필요 | ✅ 날짜별 기업 목록 |
| 주요 뉴스 | **CNBC RSS** | 불필요 | ✅ XML 정상 |
| 종목 시세 보조/폴백 | Twelve Data | 무료 키 | ✅ 단, 지수는 유료 플랜 |

## Yahoo Finance chart API (메인 시세 소스)

엔드포인트: `https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?range=2d&interval=1d`
- **`User-Agent` 헤더 필수** (없으면 차단/빈 응답).
- 응답: `chart.result[0].meta` — `regularMarketPrice`, `chartPreviousClose`
  (또는 `previousClose`)로 등락 계산. `shortName`/`longName`도 있음.

**심볼 표 (검증 완료)**:
```
현물: ^GSPC(S&P500) ^IXIC(나스닥종합) ^NDX(나스닥100) ^DJI(다우) ^RUT(러셀2000)
ETF:  SOXX(반도체) AAPL 등 개별 종목은 그대로
선물: ES=F(S&P) NQ=F(나스닥100) YM=F(다우) RTY=F(러셀2000)
원유/환율/금리: CL=F(WTI원유) DX-Y.NYB(달러인덱스) KRW=X(USD/KRW환율)
  ^VIX(공포지수) GC=F(금선물) SI=F(은선물) — 2026-08 실측 동작
  ⚠️ 금·은은 **ETF(GLD/SLV)가 아니라 선물(GC=F/SI=F) 온스당 가격으로 보고**
  — 사용자 지적("금은 gold CFD나 선물가격으로 줘, 은은 SLV가 최신 데이터 아님").
  ^TNX(10년) ^TYX(30년) — 금리 값(%) 그대로 반환
  (2년물은 Yahoo에 현물/선물 모두 제공 중단 — 사용자 판단으로 보고에서 제외)
```
- URL 인코딩 필수: `^` → `%5E` (urllib.parse.quote). **`%5E`를 또 quote하면
  이중 인코딩(`%255E`)되어 실패** — quote는 한 번만.
- ❌ `query1.finance.yahoo.com/v7/finance/quote` → **Unauthorized** (비공식
  차단됨). chart API만 사용.
- ⚠️ **프리장 데이터 없음 (실측)**: `includePrePost=true`로도 `preMarketPrice`
  는 None. 프리장/장중 방향은 24시간 거래되는 선물(ES=F 등)이 대신 반영함.

## 화제 종목 (Trending)

`https://query1.finance.yahoo.com/v1/finance/trending/US` (User-Agent 필요)
→ `finance.result[0].quotes[].symbol` — 미국 시장 화제 20개. 한국어 보고서에선
TOP 5~10만 사용.

## 실적 발표 캘린더 (Nasdaq 공식 API)

`https://api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD`
(User-Agent + Accept: application/json 필요)
→ `data.rows[]` — symbol/name/time(발표 시각)/eps/epsForecast/marketCap.
- ❌ Yahoo `/calendar/earnings` → Not Found. Twelve Data 캘린더 → 무료 티어 없음(404).

## 뉴스 (RSS)

- CNBC Markets: `https://www.cnbc.com/id/100003114/device/rss/rss.html`
  — `<item>` 파싱, description에 HTML 포함 → strip 필요.
- **기사 시간**: `<pubDate>`는 `Thu, 06 Aug 2026 12:17:28 GMT` 형식 — `%z`
  파서가 "GMT"를 못 읽으므로 **`GMT`/`UTC` → `+0000` 치환 후**
  `strptime(pub, "%a, %d %b %Y %H:%M:%S %z")` → KST로 변환해 표시.
- ❌ Stooq CSV → **JS 챌린지(PoW)로 자동화 차단**. ❌ ForexFactory 캘린더 →
  JS 렌더링이라 스크래핑 불가 (investing.com은 파싱 가능 — 위 경제 캘린더 참고).
  ❌ MarketWatch RSS → 301 (https로 리다이렉트).

## Twelve Data (보조 — Yahoo 폴백)

- 무료 키 발급: twelvedata.com/pricing (이메일 10초). **demo 키는 단일
  `/price`만 동작** — 지수/멀티 quote는 401.
- ❌ **지수(SPX 등)는 Grow/Venture 유료 플랜 전용** (404 "available starting
  with the Grow or Venture plan"). 무료 티어는 종목/ETF quote만.
- 유료 티어 제한 때문에 **지수는 Yahoo가 사실상 필수**.
- 스크립트 폴백: Yahoo 실패 시 **순수 종목/ETF(^, =F, =X 없는 심볼)만**
  `twelvedata.com/quote`로 재시도 — `.env`의 `TWELVEDATA_API_KEY`를 읽음
  (지수/선물/FX는 Twelve Data 무료 티어에서 심볼이 안 맞아 제외).

## 경제 캘린더 (연준/CPI/금리/실업률) — investing.com HTML 파싱

전용 무료 API 없음 (Twelve Data 무료에 없음, Finnhub 키 필요, BLS 403, Stooq
JS 챌린지). **investing.com 경제 캘린더 HTML 파싱은 동작함 (2026-08 실측)**:
- `https://www.investing.com/economic-calendar/` — UA 필수. 308 리다이렉트
  응답이 오므로 `curl -sL` 또는 urllib로 리다이렉트 따라가기.
- HTML(~1.2MB)에 **임베디드 JSON 이벤트 객체**가 있음. 정규식 추출:
  ```python
  objs = re.findall(r'\{[^{}]*?"event"[^{}]*?\}', html)  # 40~50개 객체
  # 각 객체: time(UTC ISO), event, eventLong, importance(1~3),
  #           currency, actual, forecast, previous
  ```
- 필터: `currency == "USD"`, `importance >= 2`, time이 오늘~+2일.
- 실제 발표값/예상/이전값까지 포함 — 실업수당 청구 ★★★, CPI, FOMC 발언 등이
  자동으로 잡힘. (실업률 자체는 월 1회(고용보고서)라 그 주엔 실업수당 청구가
  대표 고용 지표.)
- 폴백: 파싱 실패 시 뉴스 기반 감지 (CNBC RSS에서 CPI/FOMC/금리/연준 키워드
  뉴스를 LLM이 골라 보고).

## 옵션 데이터 (OI/IV/1시그마) — CBOE 지연 API

`https://cdn.cboe.com/api/global/delayed_quotes/options/{SYMBOL}.json` (UA 필요, **2026-08 실측**):
- ✅ **개별 종목(AAPL 등)**: 전체 옵션 체인 — `data.options[]`에 `bid/ask/iv(내재변동성)/open_interest(OI)/volume/delta/gamma/vega/theta` 포함. 25+ 만기, 수천 계약. `data.current_price/price_change_percent/iv30`도 제공 (연속 호출 OK, rate limit 없음 실측).
- ⚠️ **429 rate limit 실측 (2026-08)**: 순차 호출은 안전하지만 **8스레드 병렬 61연발은 429 유발**, window가 1~2분 (30~90초 대기 후 복구). 대량 조회는 **반드시 순차 + 429 시 10/30/60초 백오프 + 호출 간 1.5초 대기**. (us_market_report 20종은 순차라 무해)
- ⚠️⚠️ **`current_price`/`price_change_percent`는 애프터/프리마켓 가격을 반영함 (2026-08 실측)** — 정규장 종가가 아니다. 실적발표 직후 조회 시 급등분이 그대로 들어와 **TEAM +30.4%(CBOE) vs 실제 -2.78%(Yahoo 정규장)** 같은 오차가 발생. 등락·신호·가격 계산은 **Yahoo chart API(정규장)를 정본**으로 쓰고, CBOE는 **OI/iv30/체인 구조만** 사용할 것. (us_market_report.py 옵션 섹션의 `current_price` 사용처도 동일 리스크 — 필요 시 Yahoo 병합으로 교체)
- ✅ **SPCX(SpaceX)**: 2026년 상장됨 — 옵션 체인 존재 (IV30 ~92%). SK하이닉스 ADR = **SKHY** (나스닥).
- ❌ **SPX 등 지수 옵션**: AccessDenied (개별 종목만 가능).
- ⚠️ **전일 OI 비교 필드는 없음** → 스크립트가 `oi_snapshot.json`에 전일 총 OI를 저장하고 다음 실행에서 diff 계산 (첫 실행은 null).
- 시장 전체 OI TOP5는 무료로 불가 (CBOE 종목별 조회만) → **추적 12종 + Trending 화제 8종(최대 20종) 조회 후 TOP5** 산출. 화제 종목 중 `-USD`(암호화폐)는 제외.
- 계약명 형식: `AAPL260805C00205000` = AAPL 2026-08-05 콜 strike 205 (4자리% 인코딩: 00205000 → 205.00).
- **1시그마(1SD) 계산**: `1SD(30일) ≈ price × iv30 × √(30/365)`. ⚠️ **CBOE `iv30`은 백분율 포인트 값** (예: 42.686 = 42.7%) — 소수로 변환(`/100`) 후 계산해야 함. 옵션별 `iv` 필드는 소수(0~1)라 그대로 사용.
- 계약명에서 strike/타입 파싱: 마지막 8자리=`strike×1000`, 9번째 문자=`C/P`.
- Yahoo `/v7/finance/options` → **"Invalid Crumb" 차단 (실측)** — CBOE가 무료 경로.

## Hermes 크론 보고 패턴 (스크립트 수집 → LLM 번역 → 텔레그램)

1. **수집 스크립트** (`~/AppData/Local/hermes/scripts/us_market_report.py`):
   Yahoo(시세+trending) + Nasdaq(실적) + CNBC(뉴스) → JSON stdout.
   토큰 0원 (LLM 호출 없음).
2. **크론잡 2개** (cronjob tool, `no_agent=false`): script 지정 → stdout이
   LLM 프롬프트에 주입 → 한국어 보고서 생성 → `deliver: telegram:<chat_id>`.
   - 아침 7시(`0 7 * * *`) = 전일 장 마감 요약 / 저녁 9시(`0 21 * * *`) =
     선물 방향 + 장 전망. KST 시스템이면 그대로.
   - LLM은 뉴스 번역·요약만 — 데이터는 스크립트가 수집하므로 실패해도
     스크립트 오류 항목은 제외하고 나머지로 보고.
3. **비용**: 수집 $0 + 번역 ~$0.01/회 (뉴스 8건 기준).

### 옵션플로우 브리핑 크론 2개 (2026-08 추가 — 무료 소스)

샘플(유료 플로우 데이터)을 무료 소스로 재현한 별도 브리핑. **다크풀·실시간 플로우 체결은 무료 불가 → OI 증감 + 자체 컨빅션 스코어로 대체** (소스 표기: `스크리너·OI증감·컨빅션·1σ이탈 (무료 소스)`).

- **스크립트**: `option_flow_report.py open|close` (래퍼: `option_flow_open.py` / `option_flow_close.py`).
- **가격 정본 (필수)**: `fetch_cboe`는 OI/IV만 반환, 가격·등락은 **Yahoo 정규장(`yahoo_quote`)을 병합** — CBOE `current_price`는 애프터/프리마켓 반영이라 신호가 왜곡됨 (TEAM +30.4% 가짜 신호 실측). `signal_price`도 Yahoo 종가로 저장해야 다음 실행의 결과 검증과 기준이 일치함.
- **유니버스 61종**: 고정 56(기존12+반도체13+SW13+핀테크8+대형10) + Trending 5. CBOE 콜/풋 **총 OI 분리 집계** (계약명 9번째 문자 C/P).
- **신호 규칙**: 🔴풋 = 풋 OI +≥10% & 주가 ≤-1% / 🟢콜 = 콜 OI +≥10% & 주가 ≥+1%. 컨빅션 스코어 = OI변동35 + 주가30 + IV20 + 1σ보너스15 (0~100, 자체 공식).
- **1σ 이탈**: |일간 변동%| > iv30×√(30/365)×100.
- **시장 백드롭**: 지수4종+SOXX+VIX 조합 → -100~+100 + 레이블(strong_bearish~strong_bullish).
- **결과 검증**: 전일 신호를 `flow_signals.json`에 저장 → 다음 실행에서 Yahoo OHLC로 종가/고점/저점 % 계산 + hit/miss 판정. OI 스냅샷은 `flow_oi_snapshot.json` (기존 `oi_snapshot.json`과 **별도 파일** — 충돌 방지).
- **크론**: 장 시작 `30 22 * * 1-5` (open, 22:30 KST) / 장 종료 `5 5 * * 2-6` (close, 05:05 KST) → 주식 토픽. **첫 실행은 스냅샷 프라이밍이라 신호 0건 정상**, 두 번째부터 OI 비교 시작. 겨울 DST면 ET 기준 +1h 이동.

### 텔레그램 보고 가독성 (사용자 선호 — 2026-08 확정)

- **한 줄 항목** 형식 (`NVDA $221.81 (+1.18%) | IV30 42.8% | 1SD ±$27.2 | OI 1,456만 (+12만)`) — **markdown 표 금지** (모바일에서 잘림).
- **섹션 사이 빈 줄** 필수 — 이모지(📈⚡💵😱🥇🏦🔥🏢📰📅🎯)로 섹션 구분.
- **옵션 섹션은 항상 맨 마지막** (가독성 저하 방지 — 사용자 지시).
- 데이터 기준일 표기 (`data_date` — \"현물 8/5 종가 기준\" 같은 컨텍스트 필요).
- VIX는 값에 따라 한 줄 코멘트 (15 이하=안정, 20 이상=불안). 금리는 %p/bps로.

## Pitfalls

- ⚠️ **등락 계산 함정 (사용자가 "이틀 전 거 아냐?"로 지적)**: `range=2d`면
  `meta.chartPreviousClose`가 **첫 캔들 이전 종가**(즉 이틀 전)를 반환 → 등락이
  이틀 치로 계산됨. 해결: `range=5d`로 요청하고 **캔들 배열의 마지막 2개 유효
  종가**(`timestamp`+`close`, None 제외)로 prev를 계산. 캔들 기반 등락은
  데이터 기준일(`data_date`)도 함께 표기.
- 금리(^TNX/^TYX/2YY=F) 등락은 %가 아니라 **%p 또는 bps**로 표기
  (2YY=F가 -4.55%처럼 보이는 건 수익률의 % 변화일 뿐, 실제는 -19bps 하락).
- Yahoo는 비공식 API라 차단될 수 있음 → Twelve Data를 종목/ETF 폴백으로 두면
  안정적 (지수는 Yahoo가 유일한 무료 경로).
- 실적 API의 `eps` 값은 time(발표 시각)과 함께 오는데 일부 행은 비어있음 —
  LLM에게 "빈 값 생략" 규칙을 프롬프트에 포함.
- 크론잡 LLM 프롬프트에 "error 포함 항목 제외, 빈 섹션 생략, 뉴스는 한국어
  번역" 규칙을 항상 명시.
