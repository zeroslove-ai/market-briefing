# Hermes R1 — Core Market Indicators Authority

Status: DATA / OUTPUT AUTHORITY
Purpose: Email Full + Telegram Compact에서 항상 보여줄 핵심 시장 지표 정의

## 1. 목표

Morning 06:30 KST 브리핑에서 “오늘 시장이 어떤 상태인지”를 10~15초 안에 파악할 수 있는 핵심 지표 블록을 만든다.

원칙:
- 너무 많은 종목 나열 금지
- 자산군별 대표 1~3개
- 가격 + 등락 + 의미를 분리
- Telegram은 2~3줄 압축
- Email은 표/상세 해설 가능
- 모든 값은 동일 canonical snapshot에서 생성

## 2. Equity / Index

필수:
- S&P 500 (^GSPC)
- Nasdaq Composite (^IXIC)
- Nasdaq 100 (^NDX)
- Dow (^DJI)
- Russell 2000 (^RUT)
- SOXX

Telegram 기본 노출:
- S&P
- Nasdaq
- Russell
- SOXX

Dow/NDX는 공간에 따라 보조.

## 3. Futures

필수:
- ES=F
- NQ=F
- YM=F
- RTY=F

Morning 06:30 KST에서는 미국 현물 마감 이후이므로:
- “다음 세션 선물 방향”과 혼동하지 않도록 data timestamp를 명확히 표시
- futures data가 새 세션을 이미 반영하는 경우 별도 `post_close_futures` 블록으로 구분

Telegram:
`선물 ES +0.2% | NQ +0.3% | RTY -0.1%`

## 4. Rates / Volatility

필수:
- US 10Y (^TNX)
- US 30Y (^TYX)
- VIX (^VIX)

향후 2Y는 안정된 source 확보 후 추가.

표기:
- 금리 레벨 %
- 변화는 bp

예:
`10Y 4.97% (+5bp) | VIX 14.2 (-4.4%)`

## 5. FX

필수:
- DXY (DX-Y.NYB)
- USD/KRW (KRW=X)

Email:
- level
- daily change
- 중급자 해설

Telegram:
`DXY 100.5 +0.1% | USD/KRW 1,3xx`

## 6. Commodities

필수:
- WTI (CL=F)
- Gold (GC=F)
- Silver (SI=F)

선택:
- Brent source 별도 검증 후 추가

Telegram:
`WTI $90.0 -6.0% | Gold $x,xxx +x.x% | Silver $xx.xx`

금/은은 ETF가 아닌 선물 기준.

## 7. Crypto

R1 기본:
- Bitcoin BTC-USD
- Ethereum ETH-USD

Primary source policy:
1. Coinbase public market data adapter
2. Yahoo crypto chart fallback

Crypto는 24/7이므로 주식의 “전일 종가 대비”와 동일 개념으로 섞지 않는다.

필드:
- current_price
- 24h_change_pct
- high_24h
- low_24h
- source_timestamp

Telegram:
`BTC $xx,xxx (+x.x% 24h) | ETH $x,xxx (+x.x% 24h)`

명확히 `24h` 표기.

## 8. Telegram Market Board

기본 형식:

```text
📊 주요 지표
주식 S&P -0.0% | Nasdaq +0.45% | Russell +0.51% | SOXX ...
금리/변동 10Y 4.97% (+1bp) | VIX 14.2 (-4.4%) | DXY 100.5
원자재 WTI $90.0 (-6.0%) | Gold ... | Silver ...
크립토 BTC ... (+x.x% 24h) | ETH ... (+x.x% 24h)
```

선물은 current phase에 유의미하면 별도 1줄:
`선물 ES ... | NQ ... | RTY ...`

## 9. Email Market Board

Email은 다음 column 권장:
- Asset
- Price
- Change
- Reference window
- Interpretation

예:
- BTC: 24h
- equities: prior US regular close
- futures: latest timestamp
- yields: level + bp change

서로 다른 reference window를 같은 %처럼 오해하지 않게 명시.

## 10. Data Quality

각 지표:
- source
- timestamp
- session/reference window
- stale flag

Telegram은 stale value를 숨기거나 `⚠️ 지연` 표기.

## 11. Implementation

제안 adapter:
- `market_equity.py`
- `market_macro.py`
- `market_crypto.py`

canonical payload:

```json
{
  "indicators": {
    "equities": {},
    "futures": {},
    "rates": {},
    "volatility": {},
    "fx": {},
    "commodities": {},
    "crypto": {}
  }
}
```

## 12. DoD

- Telegram에 주식/금리/VIX/달러/WTI/금/은/BTC/ETH 표시
- Email 상세 표 지원
- reference window 명확
- crypto 24h와 equity daily change 혼동 없음
- stale timestamp 검증
