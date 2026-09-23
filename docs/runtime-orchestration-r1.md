# Hermes R1 — Runtime / Orchestration Strategy

Status: ARCHITECTURE AUTHORITY
Reviewed: 2026-09-23

목표: Hermes 하나에 종속되지 않고, 데이터 수집·계산·해설·브라우저 조사·개발 작업을 역할별로 분리해 가장 안정적으로 운영한다.

## 1. 핵심 원칙

**시장 데이터 수집과 핵심 계산은 AI 에이전트가 직접 담당하지 않는다.**

코어:
- Python deterministic collectors
- state/date/session logic
- Sigma/OI/breadth/evidence feature calculation
- JSON artifacts
- idempotency / retries / health checks

에이전트:
- 한국어 설명
- 뉴스 심층 조사
- browser-only evidence
- 코드 수정/테스트
- 장애 원인 조사

즉:

`scheduler -> deterministic pipeline -> normalized JSON -> narrative adapter -> delivery`

Narrative adapter는 Hermes/OpenAI/Grok 등으로 교체 가능하게 만든다.

## 2. 권장 운영 구조

### Primary Core Runner

가장 안정적인 production 목표:

**항상 켜진 Linux VPS 또는 유사한 always-on runner + OS-level systemd timer/cron**

이유:
- PC sleep/reboot와 독립
- AI 서비스 장애와 독립
- Python script를 직접 실행
- exit code/log/retry 관리 용이
- Hermes/Cursor/Grok 사용량과 무관

초기에는 현재 Hermes gateway를 그대로 사용할 수 있지만, production scheduler authority는 OS timer로 이동할 수 있게 script entrypoint를 분리한다.

권장 phase command:

```bash
python -m market_briefing run --phase morning
python -m market_briefing run --phase evening
python -m market_briefing run --phase open
python -m market_briefing run --phase close
```

pipeline이:
1. data collect
2. normalize
3. calculate
4. validate
5. save artifact
6. narrative job
7. Telegram delivery

를 수행한다.

### Hermes role

Hermes는 제거하지 않는다.

잘 맞는 역할:
- Telegram delivery
- scheduled agent narrative
- provider fallback
- no-agent watchdog
- ad-hoc chat
- skills

Hermes cron은 fallback/compatibility lane으로 유지하고, core script는 Hermes 없이도 실행 가능해야 한다.

Hermes의 강점:
- script-only/no-agent mode
- provider fallback
- Telegram topic delivery
- webhook/event wake
- fresh agent sessions

주의:
- local gateway라면 PC uptime 의존
- production 핵심은 agent scheduler 자체보다 script artifact여야 함

## 3. Cursor Pro / Cloud Agents / Automations

현재 Cursor Pro는 MCP, skills, hooks, Cloud Agents, Grok Bot access를 포함한다.

R1에서 가장 좋은 용도:

### 개발 lane
- Issue -> branch -> code -> tests -> PR
- CI failure repair
- scheduled code health checks
- dependency/quality audits

### automation lane
Cursor Automations:
- schedule
- GitHub events
- webhook
- CI completed
- issue/comment triggers
- MCP tools

시장 보고 자체도 실행할 수 있으나 **매번 Cloud Agent를 띄우는 것은 deterministic report runner보다 비용/복잡도가 높다.**

따라서:
- production report core: 비추천
- repo maintenance / QA / repair: 매우 추천
- watchdog / missing-report investigation: 추천

## 4. Grok Bot

Grok Bot은 persistent cloud computer, browser/filesystem/terminal, routines, multi-bot coordination을 제공한다.

좋은 역할:
- browser-heavy research bot
- 아침 뉴스 추가 조사
- 로그인 필요한 데이터/페이지 조사
- 반복 리서치 routine
- 사람이 해야 했던 multi-app research

R1 추천 bot 예:

### Market Research Bot
- 공식 source 우선
- 기사 cluster 보강
- unusual story만 심층 조사
- evidence URL/스크린샷 반환
- production JSON 수정 금지

### Filing Research Bot
- SEC filing/IR page/기업 사이트 조사
- 핵심 변화/리스크 추출
- canonical link 반환

### QA Bot
- Telegram 결과/웹 대시보드 확인
- missing section/report 이상 탐지

주의:
- 2026-09-23 기준 beta
- weekly usage meter
- browser site/session automation 특성상 deterministic collector 대체용으로 쓰지 않음
- Bot 간 shared cloud computer의 파일/browser login 범위를 고려

결론:
**Research worker로 좋고, canonical market pipeline으로는 아직 두지 않는다.**

## 5. Aside

Aside는 로그인된 실제 브라우저를 CLI/MCP/REPL로 외부 coding agent에 제공할 수 있다.

R1에서 좋은 역할:

- 로그인이 필요한 dashboard
- browser-only page
- JS-heavy site
- CSV/PDF 다운로드
- screenshot/evidence
- staging/dashboard QA
- Codex/Cursor와 결합한 private browser evidence

권장 연결:

`Codex/Cursor -> Aside MCP -> logged-in browser`

특히 coding agent가:
- GitHub Actions UI
- Vercel dashboard
- Supabase console
- private admin
- broker/research page

등을 “보기” 위한 sidecar로 좋다.

주의:
- browser state/permission/UI 변화에 의존
- private account 작업의 승인 boundary 필요
- local execution이면 PC uptime 영향
- 핵심 가격/공식뉴스 collector를 Aside에 의존하지 않는다

결론:
**Browser sidecar로 매우 좋고, core scheduler로는 부적합.**

## 6. Codex CLI / MCP / ChatGPT-connected development

Codex는 외부 MCP 서버에 연결할 수 있으므로:

- GitHub
- Aside
- Supabase
- custom market MCP

등을 한 agent에 연결할 수 있다.

중요:
**Codex를 MCP server로 노출하는 구형 방식은 현재 제거되었고**, 외부 tool을 Codex에 붙이는 방향은 계속 지원된다.

Codex의 추천 역할:
- core Python 개발
- tests
- refactor
- issue/PR work
- data source adapters
- incident repair
- documentation

항상 켜진 scheduler 역할은 맡기지 않는다.

### OpenAI Agents API

2026-09 현재 public beta.

장점:
- managed Codex harness
- durable sessions
- async turns
- webhooks
- OpenAI-hosted sandbox
- MCP
- long-running agent workflow

향후 좋은 후보:
- 뉴스 심층 synthesis service
- failed report recovery agent
- analyst session
- multi-agent evidence review

하지만 R1 production scheduler 1순위로 즉시 넣기보다는 **beta evaluation lane**으로 둔다.

## 7. GitHub Actions

좋은 역할:
- CI/tests
- nightly regression
- public source smoke tests
- backup watchdog
- manual workflow_dispatch
- recovery trigger

Primary market scheduler로만 쓰는 것은 권장하지 않는다.

이유:
- scheduled workflow는 load에 따라 지연 가능
- 드물게 queued scheduled job이 drop될 수 있음

권장:
- primary report timestamp를 확인하는 watchdog
- 일정 시간 이상 누락 시 fallback job 수행 또는 alert

## 8. 권장 Multi-Lane Architecture

```text
                    ┌──────────────────┐
                    │ OS timer / VPS   │
                    │ PRIMARY SCHEDULER│
                    └────────┬─────────┘
                             │
                    deterministic Python
                             │
                    ┌────────▼──────────┐
                    │ Canonical JSON     │
                    │ state/history      │
                    └──────┬─────┬──────┘
                           │     │
             ┌─────────────┘     └──────────────┐
             │                                  │
     Narrative Adapter                    News Research
             │                                  │
   Hermes / OpenAI API                  Grok Bot / Aside
             │                                  │
        Telegram                          evidence only

Development / Repair:
Codex + GitHub + Aside MCP
Cursor Cloud Agents / Automations

Watchdog:
GitHub Actions / Hermes no-agent
```

## 9. Provider abstraction

예:

```python
NarrativeProvider:
    explain(payload) -> report

ResearchProvider:
    investigate(query, evidence) -> research_result

DeliveryProvider:
    send(report)
```

지원 adapter 예:
- `HermesNarrativeProvider`
- `OpenAINarrativeProvider`
- `GrokNarrativeProvider`

provider failure 시 canonical JSON은 이미 저장되어 있으므로 report 재생성이 가능하다.

## 10. Reliability mechanisms

필수:

### Idempotency
`session_date + phase + schema_version` unique key.

같은 close report 두 번 전송 금지.

### Atomic artifact
Narrative 생성 전에 canonical JSON 저장.

### Retry
- network source별 retry/backoff
- LLM provider retry/fallback 분리
- Telegram retry 분리

### Health heartbeat
각 phase:
- scheduled_at
- started_at
- completed_at
- delivered_at
- status

### Watchdog
예:
- close report 예정 +20분에도 completed 없음 -> alert
- narrative 실패 -> alternate provider로 재생성
- source 일부 실패 -> degraded report

### Degraded Mode
모든 source가 정상일 필요 없음.

예:
CBOE failure:
- 가격/뉴스/거시 report는 발행
- options section degraded 표시

CNBC failure:
- SEC/Fed/official macro + market data로 발행

LLM failure:
- deterministic compact fallback template로 Telegram 발행

## 11. 가장 추천하는 역할 분담

### Production core
1. OS scheduler / VPS
2. Python
3. durable JSON/state
4. Telegram

### Primary narrative
Hermes 또는 직접 API adapter.

현재 기존 자산 재사용 측면에서는 Hermes가 가장 쉬움.

### Deep research
Grok Bot.

### Private browser evidence
Aside.

### Code / maintenance
Codex + GitHub MCP + Aside MCP.

### Cloud repair / PR automation
Cursor Cloud Agents / Automations.

### Future managed agent runtime
OpenAI Agents API evaluation.

## 12. Stability verdict

**하나만 선택하지 않는다. 역할별로 가장 안정적인 도구를 쓴다.**

Core scheduler:
- OS/VPS

Deterministic calculation:
- Python

Narrative:
- Hermes first, adapterized

Research:
- Grok Bot

Private browser:
- Aside

Development:
- Codex

Cloud repo automation:
- Cursor

Watchdog:
- GitHub Actions + no-agent lane

이 구조는 어떤 AI 제품 하나가 사용량 제한, 로그인 문제, model outage, beta regression이 생겨도 canonical market data와 report pipeline 전체가 멈추지 않게 한다.

## 13. Migration

### Stage A
현재 Hermes scripts를 하나의 common pipeline으로 정리.

### Stage B
OS scheduler entrypoint + heartbeat + artifact.

### Stage C
Hermes narrative adapter 분리.

### Stage D
Cursor/Codex development automation.

### Stage E
Grok/Aside optional research enrichment.

### Stage F
OpenAI Agents API evaluation/fallback.

R1 production은 Stage C까지만으로도 충분히 안정적이며, D/E/F는 core와 독립적으로 붙인다.
