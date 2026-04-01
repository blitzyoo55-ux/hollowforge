# HollowForge Ops Pilot Baseline Runner Design

Date: 2026-04-01

## Goal

파일럿 시작 전에 필요한 baseline checks를 한 번에 실행하고,
결과를 `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`
의 `## Baseline` 섹션에 자동 기록하는 운영용 runner를 추가한다.

이번 변경의 목적은 세 가지다.

- pilot 시작 장벽을 낮춘다.
- backend, frontend, provider resolution, story planner smoke 결과를 한 번에
  수집한다.
- 사람이 결과를 복사해 pilot log에 다시 적는 수작업을 없앤다.

## Non-Goals

이번 설계는 아래를 하지 않는다.

- backend/frontend 프로세스 자동 기동
- queue 생성, publish job 생성, DB write recovery
- `## Episode Runs`, `## Ready Queue`, `## Publishing Pilot` 섹션 자동 갱신
- frontend `npm run build`를 baseline 기본 체크에 포함
- ready queue/publishing automation까지 한 번에 CLI화

## Why This Scope

현재 HollowForge에는 개별 smoke/test 진입점은 있지만, pilot 시작 전에 필요한
check들이 분산되어 있다.

- backend target pytest
- adult provider resolution 확인
- story planner smoke
- frontend test

이 상태에서는 operator가 여러 명령을 직접 기억해야 하고, 결과를 pilot log에
수기로 옮겨 적어야 한다. 지금 필요한 것은 큰 운영 프레임워크가 아니라, pilot
시작 전에 "지금 이 상태로 돌려도 되는가"를 빠르게 확인하는 작고 명확한 도구다.

따라서 이번 범위는 `check-only baseline runner + pilot log baseline update`
로 제한한다.

## Current System Fit

현재 관련 구조는 이렇게 나뉜다.

- `backend/scripts/launch_story_planner_smoke.py`
  - live API에 붙어 story planner preview와 anchor queue handoff를 확인한다.
- `frontend/package.json`
  - 기본 UI regression entrypoint로 `npm test`를 제공한다.
- `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`
  - pilot 실행 로그 템플릿을 제공하지만, 아직 baseline 기록이 자동화돼 있지
    않다.
- adult provider resolution
  - 최근 변경으로 prompt-facing adult default와 sequence runtime adult default가
    분리되었다. pilot 시작 전 이 설정이 의도대로 유지되는지 빠르게 확인할
    필요가 있다.

즉 이번 도구는 새 운영 시스템이 아니라, 이미 있는 test/smoke/doc entrypoint를
하나의 baseline execution path로 묶는 역할을 한다.

## Approaches Considered

### 1. Shell wrapper

기존 `pytest`, smoke script, `npm test`를 bash로 묶고 Markdown 파일을 단순
문자열 치환으로 갱신하는 방식이다.

장점:

- 가장 빠르게 만들 수 있다.

단점:

- 실패 원인과 결과 요약을 구조적으로 다루기 어렵다.
- Markdown 갱신이 취약해지기 쉽다.
- `--dry-run`과 부분 실패 요약 확장이 금방 불편해진다.

### 2. Python baseline runner

추천 접근이다.

장점:

- 체크 결과를 구조적으로 수집하고 콘솔/로그 양쪽으로 재사용할 수 있다.
- `--dry-run` 지원이 자연스럽다.
- 첫 실패에서 멈추지 않고 끝까지 실행한 뒤 요약하기 쉽다.
- 이후 ready/publishing automation으로 확장하기 좋다.

단점:

- shell wrapper보다 구현량이 약간 늘어난다.

### 3. Full ops CLI

baseline뿐 아니라 brief/log/retro, ready queue, publishing pilot까지 한 CLI로
묶는 방식이다.

장점:

- 장기적으로는 운영 도구 구성이 통일된다.

단점:

- 이번 요구보다 범위가 크다.
- pilot 시작 장벽 완화라는 immediate goal을 흐릴 수 있다.

이번 요구에는 과하다.

## Chosen Design

추천안 2를 채택한다.

새 Python runner를 추가해 baseline checks를 순차 실행하고, 항목별 결과를
구조화해 콘솔과 pilot log의 `## Baseline` 섹션에 동시에 반영한다.

핵심 설계는 아래와 같다.

1. 새 entrypoint는 `backend/scripts/run_ops_pilot_baseline.py`로 둔다.
2. 기본 실행은 네 체크를 모두 수행한다.
3. 실패해도 중간에 멈추지 않고 끝까지 실행한다.
4. 기본 동작은 pilot log 자동 갱신이며, `--dry-run`이면 파일은 수정하지
   않는다.
5. service start/recovery는 범위에서 제외하고, 이미 떠 있는 상태를 확인만
   한다.

## Baseline Checks

기본 baseline runner는 아래 네 가지를 순서대로 수행한다.

### 1. Backend Target Pytest

pilot baseline에 필요한 backend target suite만 실행한다. 목적은 baseline tool
자체를 만들기 위해 전체 앱 회귀를 다시 다 돌리는 것이 아니라, pilot entrypoint와
직접 맞닿는 영역이 살아 있는지 확인하는 것이다.

기본 command는 plan 단계에서 고정하되, 최소 포함 범위는 아래다.

- sequence registry / provider resolution 관련 테스트
- story planner catalog / route 테스트
- marketing / publishing handoff 관련 테스트
- sequence runtime adult default guardrail 테스트

### 2. Adult Provider Resolution Check

adult prompt-facing default가 의도대로 `adult_openrouter_grok`를 가리키고,
sequence runtime adult default는 계속 `adult_local_llm`인지를 확인한다.

이 체크는 live API 의존 없이 실행 가능해야 한다. 즉 backend settings/registry를
직접 읽거나 짧은 Python subprocess로 확인해, 서비스 미기동과 code/config drift를
분리해 볼 수 있어야 한다.

### 3. Story Planner Smoke

기존 `backend/scripts/launch_story_planner_smoke.py`를 재사용한다.

이 체크는 live API endpoint에 붙는다. 따라서 backend가 떠 있지 않거나 route가
깨져 있으면 실패로 남는다. 이 실패는 정상적인 baseline 정보로 간주한다.

기본 smoke 입력은 아래 범위를 갖는다.

- configurable `story_prompt`
- configurable `lane`
- configurable `candidate_count`
- 기본 `ui_base_url`

### 4. Frontend Test

baseline 기본 frontend gate는 `npm test`로 둔다.

`npm run build`는 중요하지만, baseline 목적은 "운영 전 즉시 깨진 것"을 빠르게
잡는 것이다. build까지 항상 묶으면 pilot 시작 속도가 떨어지므로, build는 이후
ready/publishing automation 또는 deploy check 단계에서 별도 도구로 다룬다.

## CLI Interface

runner는 인자 없이도 동작해야 하며, 최소 플래그만 제공한다.

- `--dry-run`
- `--base-url`
- `--ui-base-url`
- `--log-path`
- `--story-prompt`
- `--lane`
- `--candidate-count`

기본값은 현재 HollowForge local pilot 흐름에 맞춘다.

CLI는 사람이 읽기 쉬운 텍스트 출력을 유지한다. 각 체크마다 아래 정보를 출력한다.

- check name
- `PASS` 또는 `FAIL`
- 핵심 한 줄 summary
- 실패 시 stderr 또는 핵심 error reason
- 실행 시간

마지막에는 전체 성공 여부를 요약한다.

## Log Update Contract

자동 갱신 범위는
`docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`
의 `## Baseline` 섹션으로 제한한다.

기존 템플릿에 아래 항목을 유지 또는 추가한다.

- `backend tests:`
- `frontend tests:`
- `adult provider resolution:`
- `story planner smoke:`

`story planner smoke:` 항목에는 단순 pass/fail만이 아니라 아래 핵심 metadata를
같이 남긴다.

- `lane`
- `policy_pack_id`
- `queued_generation_count`

`--dry-run`이면 파일은 수정하지 않고, 콘솔에 "이렇게 기록될 baseline 내용"을
보여준다.

## Internal Structure

스크립트는 네 부분으로 나눈다.

### Check Runners

각 baseline check를 개별 함수로 분리한다.

- backend pytest runner
- adult provider resolution runner
- story planner smoke runner
- frontend test runner

### Result Model

각 결과는 작은 구조로 통일한다.

- `name`
- `status`
- `summary`
- `details`
- `duration_sec`

필요하면 `rendered_log_line` 같은 derived field는 renderer에서 만든다.

### Log Renderer

결과 구조를 pilot log의 `## Baseline` 섹션 텍스트로 변환한다. Markdown 템플릿을
깨뜨리지 않도록 섹션 단위 교체만 담당하고, 다른 섹션은 건드리지 않는다.

### Main Orchestrator

순서대로 모든 checks를 실행하고, 실패 여부와 무관하게 결과를 끝까지 수집한 뒤
콘솔 출력과 파일 갱신 여부를 결정한다.

## Failure Policy

첫 실패에서 멈추지 않는다.

runner는 모든 baseline checks를 끝까지 실행한 뒤:

- 항목별 `PASS/FAIL`
- 각 실패의 핵심 이유
- 전체 성공/실패

를 함께 보고한다.

exit code는 아래처럼 둔다.

- 전체 성공 시 `0`
- 하나라도 실패 시 `1`

## Operating Rules

baseline runner는 `pilot 시작 전 상태 확인` 도구다. 아래 작업은 범위에서
제외한다.

- 프로세스 기동
- DB 수정
- queue 생성
- publish job 생성
- recovery or repair

즉 이 도구는 무엇을 고치지 않고, 현재 상태를 보여주고 기록만 남긴다.

## Testing Strategy

이 작업은 `TDD`로 진행한다.

먼저 baseline runner 전용 테스트를 작성해 red-green으로 구현한다. 최소 보장 범위는
아래 세 가지다.

1. `--dry-run`일 때 pilot log 파일을 수정하지 않는다.
2. 결과 집합이 `## Baseline` 섹션 텍스트로 올바르게 렌더링된다.
3. 일부 체크가 실패해도 나머지 체크를 계속 실행하고 전체 실패 상태를 남긴다.

runner unit tests는 subprocess를 실제로 많이 띄우지 않고, 작은 실행 헬퍼를
mock/stub 해서 성공/실패/timeout 케이스를 검증한다.

마지막 verification은 새 baseline runner 테스트와 직접 영향이 있는 기존 smoke 또는
route 회귀 묶음 정도로 제한한다.

## Risks And Mitigations

- smoke check 실패 원인이 서비스 미기동인지 기능 회귀인지 혼동될 수 있다.
  - mitigation: live API 의존인 check와 code/config only check를 분리해 summary에
    명시한다.

- pilot log 템플릿이 바뀌면 섹션 치환이 깨질 수 있다.
  - mitigation: 전체 파일 overwrite가 아니라 `## Baseline` 섹션만 명시적으로
    찾고 교체한다.

- frontend `npm test`만으로 build break를 놓칠 수 있다.
  - mitigation: 이번 baseline scope는 startup gate로 제한하고, build는 후속
    ready/publishing 또는 deploy check 단계로 분리한다.

- check 결과를 너무 자세히 기록하면 pilot log가 지저분해질 수 있다.
  - mitigation: log에는 한 줄 요약만 남기고, 상세 stderr는 콘솔 출력에 둔다.

## Success Criteria

- operator가 한 명령으로 pilot baseline checks를 모두 실행할 수 있다.
- 결과가 pilot log `## Baseline` 섹션에 자동 반영된다.
- `--dry-run`으로 무해한 preview 실행이 가능하다.
- 일부 check 실패 시에도 나머지 결과가 모두 수집된다.
- adult provider resolution과 story planner smoke 상태를 분리해서 볼 수 있다.

## References

- `backend/scripts/launch_story_planner_smoke.py`
- `frontend/package.json`
- `docs/superpowers/ops/2026-03-31-hollowforge-ops-pilot-log.md`
- `docs/superpowers/specs/2026-03-31-adult-grok-default-provider-design.md`
