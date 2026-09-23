# Market Briefing — 미국 증시·옵션플로우 자동 브리핑

Hermes Agent가 **무료 데이터 소스만으로** 미국 증시와 옵션플로우를 수집해 한국어로 브리핑하는 시스템입니다. 모든 소스는 실측 검증되었고, 유료 API나 키가 필요한 서비스는 사용하지 않습니다.

- **수집 스크립트 → JSON stdout → 크론 LLM이 한국어 브리핑 생성 → 텔레그램 전달**
- 데이터 수집은 LLM 호출 없음(토큰 $0), 번역·요약만 LLM 사용(약 $0.01/회)

## 개발 예정 — Hermes R1 Integrated Market Intelligence

기존 4종 브리핑을 유지하면서 Weekly Sigma·시장/섹터 breadth·OI·금리/VIX/달러·이벤트를 함께 교차검증해 **무엇이 바뀌었고 왜 그렇게 해석하는지**를 설명하는 구조로 확장합니다.

핵심 흐름: `공통 데이터 정본 -> deterministic 분석 -> Evidence/Counter-evidence -> LLM 해설 -> Telegram`

설계 authority:

1. [`docs/hermes-integrated-intelligence-r1.md`](docs/hermes-integrated-intelligence-r1.md) — 최상위 제품/분석 정본
2. [`docs/hermes-sigma-product-spec.md`](docs/hermes-sigma-product-spec.md) — Weekly Sigma 계산 정본
3. [`docs/hermes-sigma-implementation-plan.md`](docs/hermes-sigma-implementation-plan.md) — 실제 PR 구현 순서
4. [`docs/hermes-sigma-briefing-contract.md`](docs/hermes-sigma-briefing-contract.md) — 기존 4종 보고 + 깊은 설명 규칙
5. [`docs/hermes-sigma-explainer.md`](docs/hermes-sigma-explainer.md) — 비전문가용 쉬운 해설
6. [`docs/hermes-sigma-task-board.md`](docs/hermes-sigma-task-board.md) — 실행 작업보드
7. [`docs/hermes-sigma-ai-handoff.md`](docs/hermes-sigma-ai-handoff.md) — 새 GPT/Codex/Claude 세션 인수인계

> 구현 순서는 **R1-0 Data Integrity Foundation -> R1-1 Sigma -> R1-2 Evidence Engine -> 4종 보고 통합**입니다. 기존 production 보고는 단계별 회귀 테스트로 유지합니다.

R1의 4개 보고 역할:

- 07:00: **Close Autopsy** — 전일 미국장 사후해설
- 21:00: **Pre-market Setup** — 아침 이후 변화 + 오늘 밤 관전 조건
- Opening: **Opening Watch** — setup 확인/무효화
- 05:05: **Session Verdict** — breadth/Sigma/OI 변화와 다음 세션 carry-over

현재 코드에서 R1-0로 먼저 정리할 핵심은 CBOE 가격 사용 제거, OI baseline 단일화, repo-root state 통일, ZoneInfo/DST 대응, 미국 세션 기준 날짜, 중복 fetch cache입니다.

## 결과물 (텔레그램 브리핑 4종)

| 브리핑 | 시각 (KST) | 스크립트 | 내용 |
|---|---|---|---|
| 미국 증시 아침 보고 | 매일 07:00 | `us_market_report.py` | 전일 마감 지수·선물·금리·금속·화제종목·실적·뉴스·경제캘린더·옵션(OI/IV30/1SD) |
| 미국 증시 저녁 보고 | 매일 21:00 | `us_market_report.py` | 동일 구성, 장 시작 전 전망 중심 |
| 옵션플로우 장 시작 | 월–금 22:30 | `option_flow_open.py` | 프리마켓 전망 + 전일 마감 신호(오늘 관전 포인트) + 실적·경제·뉴스 |
| 옵션플로우 장 마감 | 화–토 05:05 | `option_flow_close.py` | 시장 백드롭 + 🟢/🔴 신호 + 결과 검증 + 비정상 OI 감지 |

> 시각은 미국 정규장(09:30–16:00 ET)에 맞춘 값입니다. 미국 DST 전환 시 ET 기준 +1시간 이동합니다.

## 옵션플로우 브리핑이 하는 일

유료 옵션플로우 서비스(Unusual Whales, Cheddar Flow류)의 브리핑 형식을 **무료 소스로 재현**한 것입니다:

- **유니버스 61종**: 고정 56종(반도체·소프트웨어·핀테크·대형주) + Yahoo Trending 5종
- **비정상 OI 감지**: CBOE 옵션 체인에서 콜/풋 총 OI를 분리 집계해 전일 스냅샷과 비교
  - 🔴풋 = 풋 OI +10% 이상 & 주가 -1% 이하 (신규 숏 베팅)
  - 🟢콜 = 콜 OI +10% 이상 & 주가 +1% 이상 (신규 롱 베팅)
- **자체 컨빅션 스코어 (0–100)**: OI 변동 35 + 주가 움직임 30 + IV 레벨 20 + 1σ 이탈 15
- **1σ 이탈**: `1SD% = iv30 × √(30/365)` — 일간 변동이 이를 초과하면 플래그
- **시장 백드롭**: 지수 4종 + SOXX + VIX 조합 → -100~+100 점수 + 레이블
- **결과 검증**: 전일 신호를 저장해 두고 다음 실행에서 종가/고점/저점 % + hit/miss 판정

### 재현 불가 항목 (정직 명시)

다크풀 프린트, 실시간 옵션 체결(스윕/블록), 외부 컨빅션 스코어는 **유료 서비스 전용 데이터**라 무료로 구현할 수 없습니다. 이 시스템은 OI 증감·IV·가격 데이터로 그 **구조만** 재현합니다.

## 저장소 구조

```
scripts/
  market_clock.py         # DST-aware ET/KST session and phase resolver
  market_data.py          # Yahoo/CBOE shared cache and authority adapters
  market_board.py         # canonical cross-asset indicator collector
  state_store.py          # repo-root state + atomic writes
  report_snapshots.py     # phase snapshots and change deltas
  r1_dry_run.py           # public-data/server smoke entrypoint
  us_market_report.py       # 증시 보고 수집 (시세·뉴스·실적·경제캘린더·옵션)
  option_flow_report.py     # 옵션플로우 수집 (open/close 모드, 신호·검증·스냅샷)
  option_flow_open.py       # open 모드 진입점 (크론용)
  option_flow_close.py      # close 모드 진입점 (크론용)
state/
  oi_snapshot.json          # 증시 보고용 전일 OI 스냅샷
  flow_oi_snapshot.json     # 옵션플로우용 전일 콜/풋 OI 스냅샷 (별도 파일)
  flow_signals.json         # 전일 신호 저장 (다음 실행에서 결과 검증)
  option/                   # close-owned OI and option-flow state
  report_snapshots/         # latest_morning/evening/open/close (runtime)
  report_history/           # JSONL report history (runtime)
docs/
  data-sources.md           # 검증된 무료 소스 목록 (실측 결과 포함)
  signal-rules.md           # 신호·백드롭·검증 계산 규칙
  cron-jobs.md              # 크론잡 4개 설정 + LLM 프롬프트 전문
  pitfalls.md               # 실측으로 발견한 함정과 우회
  hermes-sigma-*.md         # Sigma Intelligence 설계/해설/구현 authority
SKILL.md                    # Hermes 운영 스킬 문서 (노하우 포함)
```

## 실행 방법

```bash
python scripts/us_market_report.py                 # 증시 보고 JSON 출력
python scripts/r1_dry_run.py --phase morning        # canonical R1 public-data smoke test
python scripts/option_flow_report.py close         # 옵션플로우 마감 (61종 CBOE 순차, ~3분)
python scripts/option_flow_report.py open          # 옵션플로우 장 시작 (~10초)
```

외부 의존성 없음 — 표준 라이브러리만 사용합니다(`urllib`, `json`, `re`, `concurrent.futures`). Python 3.8+.

## 데이터 소스

전부 무료·무키 소스입니다. 상세 실측 결과는 [docs/data-sources.md](docs/data-sources.md).

- **Yahoo Finance chart API** — 지수·선물·종목 시세, 정규장 OHLC (가격의 정본)
- **CBOE 지연 옵션 API** — 종목별 옵션 체인 (OI, IV, 1SD 계산용)
- **Nasdaq API** — 실적 발표 캘린더
- **CNBC RSS** — 시장 뉴스
- **investing.com** — 경제 캘린더 (USD, 중요도 2+)
- **Yahoo Trending** — 화제 종목

## AWS EC2 dry-run bootstrap

`deploy/bootstrap-ec2.sh` installs the minimum Ubuntu packages, creates a
virtualenv, clones `feature/hermes-r1-data-core`, and runs the canonical
`r1_dry_run.py`. The systemd unit/timers under `deploy/` are an inactive
schedule foundation; enable them only after reviewing the server state and
delivery credentials. No email/Telegram secrets are required for the dry-run.

## 라이선스

개인 용도. 데이터는 각 제공자의 이용약관을 따릅니다.
