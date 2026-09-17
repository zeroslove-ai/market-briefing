# 검증된 무료 데이터 소스

2026년 8월 실측 기준. 모든 소스는 API 키가 필요 없습니다.

| 용도 | 소스 | 실측 결과 |
|---|---|---|
| 지수/선물/종목 시세 | Yahoo chart API | ✅ 지수·선물·ETF 모두 동작 |
| 정규장 OHLC (가격 정본) | Yahoo chart (range=5d, interval=1d) | ✅ 캔들 기반 등락 계산 |
| 화제 종목 | Yahoo Trending | ✅ 20개 반환 |
| 실적 발표 캘린더 | Nasdaq API | ✅ 날짜별 기업 목록 |
| 주요 뉴스 | CNBC RSS | ✅ XML 정상 |
| 경제 캘린더 | investing.com HTML | ✅ 임베디드 JSON 파싱 가능 |
| 옵션 체인 (OI/IV) | CBOE 지연 옵션 API | ✅ 개별 종목 전체 체인 |

## Yahoo Finance chart API

```
https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}?range=5d&interval=1d
```

- **`User-Agent` 헤더 필수** — 없으면 차단/빈 응답
- 응답: `chart.result[0].meta.regularMarketPrice` + `indicators.quote[0].close[]` 캔들
- **등락 계산 함정**: `range=2d`면 `meta.chartPreviousClose`가 이틀 전 종가를 반환해 등락이 이틀 치로 계산됨. `range=5d`로 요청하고 **마지막 2개 유효 캔들**로 prev를 계산할 것
- URL 인코딩은 **한 번만** (`^` → `%5E`). 이중 인코딩(`%255E`)은 실패
- ❌ `query1.finance.yahoo.com/v7/finance/quote` → Unauthorized (비공식 차단)

### 검증된 심볼 표

```
현물: ^GSPC(S&P500) ^IXIC(나스닥종합) ^NDX(나스닥100) ^DJI(다우) ^RUT(러셀2000) SOXX(반도체)
선물: ES=F(S&P) NQ=F(나스닥100) YM=F(다우) RTY=F(러셀2000)
원유/달러/환율: CL=F(WTI) DX-Y.NYB(달러인덱스) KRW=X(USD/KRW)
변동성/금속: ^VIX GC=F(금선물) SI=F(은선물)
금리: ^TNX(10년) ^TYX(30년)   ← 값이 %로 반환됨
```

- 금·은은 ETF(GLD/SLV)가 아니라 **선물(GC=F/SI=F)** 온스당 가격을 사용
- 금리(^TNX/^TYX) 등락은 %가 아니라 **%p 또는 bps**로 표기
- 2년물은 Yahoo에 현물/선물 심볼 모두 제공 중단 → 보고에서 제외

## CBOE 지연 옵션 API

```
https://cdn.cboe.com/api/global/delayed_quotes/options/{SYMBOL}.json
```

- ✅ **개별 종목**: 전체 옵션 체인 — `data.options[]`에 `bid/ask/iv/open_interest/volume/greeks`
- `data.current_price`, `data.price_change_percent`, `data.iv30` 제공
- ⚠️ **`iv30`은 백분율 포인트 값** (예: `42.686` = 42.7%) → 1SD 계산 시 `/100`
- 계약명 형식: `AAPL260805C00205000` = AAPL 2026-08-05 콜 strike 205
  - 마지막 8자리 = strike × 1000, 9번째 문자 = C/P
- ❌ SPX 등 지수 옵션 → AccessDenied (개별 종목만)
- ❌ Yahoo `/v7/finance/options` → "Invalid Crumb" 차단

### ⚠️ 429 rate limit (실측)

| 호출 방식 | 결과 |
|---|---|
| 순차 호출 (20종) | ✅ 안전 |
| **8스레드 병렬 61연발** | ❌ **429 Too Many Requests 전면 실패** |
| 429 후 대기 | 1~2분 window, 30~90초 대기하면 복구 |

대량 조회는 **반드시 순차 + 429 시 10/30/60초 백오프 + 호출 간 1.5초 대기**.
참고: `us_market_report.py`는 20종 순차라 영향 없음.

### ⚠️ CBOE `current_price`는 애프터마켓/프리마켓 가격을 반영

실측 오류 사례 (2026-08-07):

| 종목 | CBOE 반환 | Yahoo 정규장 실제 |
|---|---|---|
| TEAM | +30.4% (143.52) | **-2.78%** (110.17) |
| ABNB | +9.1% (165.26) | **-0.56%** (151.64) |
| DOCS | +78.3% (36.8) | **-4.48%** (20.66) |

→ CBOE 가격으로 신호를 만들면 **가짜 신호**가 생성됨.
→ **가격·등락은 Yahoo 정규장을 정본으로 사용**하고, CBOE는 **OI/IV만** 사용할 것.

## 실패한 소스 (기록)

| 소스 | 실패 원인 |
|---|---|
| Stooq CSV | JS 챌린지(PoW)로 자동화 차단 |
| ForexFactory 캘린더 | JS 렌더링 |
| MarketWatch RSS | 301 리다이렉트 |
| Twelve Data (무료) | 지수는 Grow/Venture 유료 플랜 전용 (404) |
| Yahoo `/calendar/earnings` | Not Found |
| Yahoo `/v7/finance/quote` | Unauthorized |
| BLS 사이트 | 403 |
