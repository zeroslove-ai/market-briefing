# Hermes R1 — Task Board

Status: EXECUTION BOARD
Parent authority: `docs/hermes-integrated-intelligence-r1.md`

## R1-0 — Data Integrity Foundation

Sigma보다 먼저 기존 Hermes의 공통 데이터 기반을 정리한다.

### R1-0.1 Session / Time
- [ ] `ZoneInfo("America/New_York")`
- [ ] `ZoneInfo("Asia/Seoul")`
- [ ] market_session_date helper
- [ ] phase: morning/evening/open/close
- [ ] DST-aware scheduling strategy
- [ ] holiday/last-actual-session handling

### R1-0.2 State
- [ ] repo-root `state/` helper
- [ ] script-directory state write 제거
- [ ] state schema version
- [ ] session_date metadata
- [ ] atomic write

### R1-0.3 Shared Data Core
- [ ] common Yahoo regular quote/OHLC
- [ ] common CBOE option-chain parser
- [ ] per-run cache
- [ ] common Nasdaq earnings collector
- [ ] common news/econ collector
- [ ] quality flags

### R1-0.4 Existing integrity fixes
- [ ] `us_market_report.py` CBOE current_price 제거
- [ ] Yahoo regular price authority
- [ ] OI snapshot owner를 close job으로 단일화
- [ ] 아침/저녁 실행이 OI baseline을 덮어쓰지 않음
- [ ] ET candle date normalization
- [ ] US target session 기준 earnings date
- [ ] CBOE duplicate calls 감소

### R1-0.5 Report snapshots
- [ ] latest_morning/evening/open/close
- [ ] report history
- [ ] changes_since_previous_report
- [ ] same-session duplicate/no-op guard

### R1-0 PASS
- [ ] 기존 4종 보고 회귀 없음
- [ ] 동일 가격/세션 값이 보고마다 다르게 계산되지 않음
- [ ] OI “전일 대비” 기준 세션이 명확함
- [ ] DST 수동 숫자 하드코딩 제거 가능

---

## R1-1 — Weekly Sigma Core

### R1-1.1 Foundation
- [ ] `config/sigma_universe.json`
- [ ] `config/sector_map.json`
- [ ] pure sigma math
- [ ] fixture tests

### R1-1.2 Weekly Builder
- [ ] target expiry
- [ ] ATM strike
- [ ] call/put ATM IV merge
- [ ] Friday/last-session anchor
- [ ] `state/sigma_week.json`
- [ ] quality flags
- [ ] CBOE backoff/cache

### R1-1.3 Daily State
- [ ] weekly z
- [ ] status
- [ ] delta-z
- [ ] new breakout
- [ ] re-entry
- [ ] breach age
- [ ] max abs z
- [ ] history

### R1-1.4 Breadth
- [ ] market mean/median z
- [ ] ±1σ / ±1.5σ counts
- [ ] near-edge counts
- [ ] sector mean/median
- [ ] sector breach ratio
- [ ] delta median z
- [ ] watchlists

### R1-1.5 Previous week
- [ ] rollover
- [ ] previous final z
- [ ] repeated direction
- [ ] rollover tests

---

## R1-2 — Evidence Engine

### R1-2.1 Market state
- [ ] direction
- [ ] breadth state
- [ ] volatility state
- [ ] rates impulse
- [ ] USD impulse
- [ ] cross-asset confirmation

### R1-2.2 Evidence objects
- [ ] observation
- [ ] support
- [ ] counter-evidence
- [ ] confidence HIGH/MEDIUM/LOW
- [ ] source/field references
- [ ] quality suppression

### R1-2.3 Claim families
- [ ] BREADTH_DOWN/UP
- [ ] sector-led weakness/strength
- [ ] RISK_OFF/RISK_ON confirmation
- [ ] CROSS_ASSET_MIXED
- [ ] RATES_HEADWIND_GROWTH
- [ ] VOLATILITY_EXPANSION
- [ ] IDIOSYNCRATIC_MOVE
- [ ] SIGMA_OI_CONFIRMED/CONFLICT
- [ ] EVENT_RISK_DOMINANT
- [ ] REENTRY_AFTER_EXTREME

### R1-2.4 Watch ranking
- [ ] significance
- [ ] freshness
- [ ] confluence
- [ ] data quality
- [ ] avoid duplicate ticker narratives

---

## R1-3 — Existing OI + Sigma Integration

### Preserve legacy
- [ ] legacy market_backdrop remains available
- [ ] legacy conviction remains available
- [ ] score breakdown exposed

### New confluence
- [ ] SIGMA_ONLY
- [ ] OI_ONLY
- [ ] SIGMA_OI_CONFIRMED
- [ ] CONFLICT
- [ ] BREADTH_CONFIRMED
- [ ] EVENT_CONTEXT

### Verification
- [ ] next close only hit/miss 외 +1/+3/+5 session outcome 저장
- [ ] max favorable/adverse excursion
- [ ] re-entry 여부
- [ ] no probability claims before calibration

---

## R1-4 — Four-report Integration

### 07:00 Close Autopsy
- [ ] legacy market data
- [ ] Sigma Map
- [ ] sector breadth
- [ ] state transitions
- [ ] OI confluence
- [ ] catalyst candidates
- [ ] carry-over
- [ ] Layer 1/2/3 explanation

### 21:00 Setup
- [ ] changes since morning
- [ ] futures/rates/VIX/USD
- [ ] event risk
- [ ] ±1σ edge watch
- [ ] prior signal status
- [ ] 3~5 confirm/invalidate checks

### Opening Watch
- [ ] changes since evening
- [ ] regular_z vs indicative_z
- [ ] opening gap
- [ ] event reaction
- [ ] confirm/invalidate

### 05:05 Session Verdict
- [ ] changes since open
- [ ] breadth/sector rotation
- [ ] Sigma transitions
- [ ] fresh OI
- [ ] thesis verification
- [ ] carry-over

---

## R1-5 — Explanation QA

- [ ] LLM does not recalculate
- [ ] no missing-value invention
- [ ] no unsupported causality
- [ ] counter-evidence used when present
- [ ] 1σ beginner explanation
- [ ] Telegram no wide markdown tables
- [ ] important numbers remain available
- [ ] same payload -> materially consistent briefing

---

## R1-6 — Historical Validation

- [ ] SIGMA_ONLY outcomes
- [ ] OI_ONLY outcomes
- [ ] SIGMA_OI_CONFIRMED outcomes
- [ ] BREADTH_CONFIRMED outcomes
- [ ] REENTRY outcomes
- [ ] EXTREME outcomes
- [ ] +1/+3/+5 session forward stats
- [ ] minimum sample rule before threshold changes

---

## R2 — Gamma / UI

### Gamma concentration
- [ ] strike gamma-weighted OI
- [ ] local concentration
- [ ] second-strike ratio
- [ ] sigma edge distance
- [ ] reaction-zone candidate
- [ ] dealer-position wording guardrail

### UI
- [ ] API/export
- [ ] market distribution
- [ ] sector distribution
- [ ] symbol detail
- [ ] report-delta timeline
- [ ] previous-week compare

---

## 실행 순서

1. **R1-0 Data Integrity Foundation**
2. **R1-1 Weekly Sigma Core**
3. **R1-2 Evidence Engine**
4. **R1-3 OI/Sigma Integration**
5. **R1-4 Four-report Integration**
6. **R1-5 QA**
7. **R1-6 Validation**

첫 production PR은 Sigma math가 아니라 **공통 데이터/session/state 기반 정리**부터 시작한다.

완료 보고 형식:

`VERDICT / Branch / HEAD / Changed files / Tests / Evidence / Known limitations / Next`
