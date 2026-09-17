# Hermes Sigma — Task Board (R0)

이 문서는 Issue가 없는 환경에서도 다른 AI가 즉시 작업을 쪼갤 수 있도록 만든 작업 보드다.

## EPIC S1 — Weekly Sigma Core

### S1-1 Foundation
- [ ] `ZoneInfo("America/New_York")` / `Asia/Seoul` 도입
- [ ] repo-root `state/` path helper 통일
- [ ] `config/sigma_universe.json`
- [ ] `config/sector_map.json`
- [ ] pure sigma math 함수
- [ ] math fixture tests

### S1-2 Weekly Builder
- [ ] target expiry 선택
- [ ] ATM strike 선택
- [ ] call/put ATM IV merge
- [ ] Friday/last-session anchor
- [ ] `state/sigma_week.json`
- [ ] quality flags
- [ ] CBOE 429 backoff 유지

### S1-3 Daily State
- [ ] current regular price
- [ ] z-score
- [ ] status
- [ ] delta-z
- [ ] new breakout
- [ ] re-entry
- [ ] breach age
- [ ] max abs z
- [ ] daily history

### S1-4 Breadth
- [ ] mean/median z
- [ ] ±1σ counts
- [ ] ±1.5σ counts
- [ ] near-edge counts
- [ ] sector median/mean
- [ ] sector breach ratio
- [ ] watchlists

### S1-5 History
- [ ] previous week snapshot
- [ ] repeated direction flag
- [ ] rollover tests

### S1-6 Briefing Integration
- [ ] morning Sigma Market Map
- [ ] evening edge watch
- [ ] open indicative watch
- [ ] close transition + confluence
- [ ] beginner-language prompt
- [ ] missing/stale data explanation

## EPIC S2 — OI/Gamma Confluence

### S2-1 Existing OI Merge
- [ ] sigma-only
- [ ] oi-only
- [ ] confirmed
- [ ] conflict
- [ ] breadth-confirmed

### S2-2 Gamma Concentration
- [ ] strike gamma-weighted OI
- [ ] local concentration
- [ ] second-strike ratio
- [ ] ±1σ edge distance
- [ ] reaction zone candidate
- [ ] terminology guardrails

## EPIC S3 — Validation

- [ ] 8~12주 history 축적
- [ ] threshold sensitivity review
- [ ] false/stale signal audit
- [ ] weekly sigma method comparison
- [ ] ATM IV vs straddle-implied move comparison
- [ ] sector mapping review

## EPIC S4 — UI (S1 안정화 후)

- [ ] JSON API/export
- [ ] market distribution
- [ ] sector distribution
- [ ] symbol detail
- [ ] previous-week compare
- [ ] sigma × gamma screener

## 지금 시작할 작업

`S1-1 Foundation`부터 시작한다.

완료 보고는 반드시 `VERDICT / Branch / HEAD / Changed files / Tests / Evidence / Limitations / Next` 형식으로 남긴다.
