# HollowForge Comic Verification Suite Operator Entry Design

기준일: 2026-04-17

## Goal

`HollowForge`의 comic verification 스크립트들을 사람이 쓰기 쉬운 단일 운영 진입점으로 묶는다.

이번 단계의 목표는 새 검증 로직을 만드는 것이 아니다.

- 이미 분리된 `one_panel_smoke`
- 이미 검증된 `one_panel_verification`
- 이미 검증된 `remote_render_smoke`

이 세 경로를 운영자가 한 번에 실행하거나 선택적으로 실행할 수 있게 정렬하는 것이다.

성공 기준은 아래 네 가지다.

1. 운영자는 하나의 명령으로 comic verification suite를 실행할 수 있다.
2. 기본 실행은 권장 순서인 `smoke -> full -> remote`를 따른다.
3. 각 단계는 실패 시 즉시 멈추는 `fail-fast`를 기본으로 한다.
4. 필요하면 특정 단계만 선택하거나 실패 후에도 다음 단계를 계속 실행할 수 있다.

## Current State

현재 worktree에는 아래 검증 엔트리포인트가 있다.

- `backend/scripts/launch_comic_one_panel_smoke.py`
- `backend/scripts/launch_comic_one_panel_verification.py`
- `backend/scripts/launch_comic_remote_render_smoke.py`

방금 세 경로 모두 실제 로컬 스택에서 검증했다.

- `8012 -> 8611 -> 8188`
- `one_panel_smoke`: pass
- `one_panel_verification`: pass
- `remote_render_smoke`: pass

즉 개별 경로의 신뢰도는 충분하다.

지금 부족한 것은 “어떤 순서로 무엇을 실행해야 하는지”를 운영자가 매번 기억해야 한다는 점이다.

## Problem Statement

문제는 구현 부족이 아니라 운영 표면이 분산돼 있다는 점이다.

### 1. 엔트리포인트가 분산돼 있다

현재는 운영자가 아래를 직접 기억해야 한다.

- 빠른 점검은 어느 스크립트인가
- 실제 runtime 검증은 어느 스크립트인가
- remote lane 전용 검증은 어느 스크립트인가
- 어느 순서로 돌리는 것이 안전한가

이 구조는 개발자에게는 괜찮지만 운영자에게는 불필요하게 거칠다.

### 2. 권장 순서가 코드에 고정돼 있지 않다

현재 권장 순서는 명확하다.

1. `one_panel_smoke`
2. `one_panel_verification`
3. `remote_render_smoke`

하지만 이 순서는 문맥 속에서만 존재한다.

운영자나 자동화가 순서를 틀리면 다음 문제가 생길 수 있다.

- 더 무거운 full 검증을 먼저 돌린다
- smoke에서 걸러질 문제를 full에서 뒤늦게 발견한다
- remote lane만 따로 실행해 놓고 전체 흐름이 통과했다고 오해한다

### 3. 결과 요약이 흩어진다

각 스크립트는 자체 marker를 잘 출력한다.

하지만 suite 관점에서는 아래 요약이 필요하다.

- 어떤 단계가 실행됐는가
- 어느 단계에서 실패했는가
- 전체 성공 여부는 무엇인가
- 각 단계 소요 시간은 얼마인가

현재는 이 정보를 사람이 수작업으로 합쳐야 한다.

## Non-Goals

이번 단계에서 하지 않는 것:

- 새로운 comic render recipe 추가
- quality scoring 변경
- animation verification suite 통합
- `/production` 웹 UI 변경
- queue orchestration 백엔드 서비스 추가
- 검증 결과를 DB에 영구 저장하는 기능 추가

## Considered Approaches

### 1. Shell wrapper만 추가

예를 들어 `bash` 스크립트로 세 개의 Python 스크립트를 순차 호출한다.

장점:

- 구현이 매우 빠르다

단점:

- 결과 요약을 구조적으로 다루기 어렵다
- 옵션 파싱이 약하다
- 기존 Python marker와의 통합이 거칠다
- 테스트하기 불편하다

지금 단계에서는 부족하다.

### 2. 단일 Python suite entrypoint 추가

새 Python 스크립트가 각 검증 엔트리포인트를 순차 호출하고, suite 요약을 별도로 출력한다.

장점:

- 옵션 파싱이 명확하다
- pytest로 회귀를 고정하기 쉽다
- 기존 marker 출력과 자연스럽게 맞물린다
- 향후 animation suite 확장도 쉽다

단점:

- 작은 orchestration layer를 새로 만들어야 한다

현재 목표에 가장 적합하다.

### 3. production hub smoke에 검증 기능을 혼합

기존 `launch_production_hub_smoke.py` 안에 comic verification suite까지 집어넣는다.

장점:

- 운영 허브 개념과 이어질 수 있다

단점:

- production hub 검증과 comic runtime 검증의 책임이 섞인다
- 현재 단계에서는 범위가 커진다
- 실패 원인 분리가 어려워진다

지금은 분리된 상태를 유지하는 편이 맞다.

## Recommended Direction

권장 방향은 `단일 Python suite entrypoint`다.

새 엔트리포인트는 예를 들어 아래처럼 둔다.

- `backend/scripts/run_comic_verification_suite.py`

이 스크립트는 세 단계의 orchestration만 책임진다.

1. `one_panel_smoke`
2. `one_panel_verification`
3. `remote_render_smoke`

실제 검증 세부 동작은 기존 스크립트가 계속 책임진다.

즉 suite는 “새 검증 엔진”이 아니라 “운영자용 조합기”다.

## Operator Contract

### Default behavior

기본 실행은 아래 순서를 따른다.

1. `one_panel_smoke`
2. `one_panel_verification`
3. `remote_render_smoke`

기본 정책은 `fail-fast`다.

어느 한 단계라도 실패하면:

- suite는 즉시 종료한다
- 다음 단계는 실행하지 않는다
- `failed_stage`를 출력한다

이 기본값이 가장 안전하다.

### Selective execution

운영자는 특정 단계만 선택해서 실행할 수 있어야 한다.

최소 옵션은 아래 정도면 충분하다.

- `--smoke-only`
- `--full-only`
- `--remote-only`

복수 선택은 이번 단계에서는 넣지 않는다.

이유는 간단하다.

- 표면을 작게 유지한다
- 잘못된 조합을 줄인다
- 필요하면 나중에 `--stages smoke,remote` 같은 일반화된 구조로 확장할 수 있다

### Continue-on-failure

기본은 `fail-fast`지만, 운영자가 전체 상황을 한 번에 보고 싶을 때를 위해 아래 옵션을 둔다.

- `--continue-on-failure`

이 옵션이 켜지면:

- 실패해도 다음 단계로 진행한다
- 마지막에 전체 summary를 출력한다
- 단, `overall_success`는 모든 단계 성공일 때만 `true`다

## CLI Surface

예상 표면은 아래와 같다.

### Default

```bash
python3 backend/scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8012
```

### Smoke only

```bash
python3 backend/scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8012 --smoke-only
```

### Full only

```bash
python3 backend/scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8012 --full-only
```

### Remote only

```bash
python3 backend/scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8012 --remote-only
```

### Continue on failure

```bash
python3 backend/scripts/run_comic_verification_suite.py --base-url http://127.0.0.1:8012 --continue-on-failure
```

## Execution Model

suite runner는 기존 스크립트를 subprocess로 호출하는 방식이 가장 적합하다.

이유는 아래와 같다.

- 기존 marker 출력 형식을 그대로 보존할 수 있다
- 각 스크립트의 `main()` import side effect를 억지로 얽지 않아도 된다
- exit code를 단계별로 분리해서 다루기 쉽다
- 운영자 입장에서 실제 호출 관계가 명확하다

즉 suite는 각 스크립트를 아래처럼 실행한다.

- `python3 backend/scripts/launch_comic_one_panel_smoke.py ...`
- `python3 backend/scripts/launch_comic_one_panel_verification.py ...`
- `python3 backend/scripts/launch_comic_remote_render_smoke.py ...`

## Output Contract

하위 스크립트의 marker 출력은 그대로 유지한다.

suite는 그 위에 상위 summary를 덧붙인다.

최소 marker는 아래 정도가 적절하다.

- `suite_mode`
- `base_url`
- `stages_requested`
- `stages_completed`
- `failed_stage`
- `overall_success`
- `continue_on_failure`
- `total_duration_sec`

단계별 요약도 함께 출력한다.

- `stage_smoke_exit_code`
- `stage_smoke_duration_sec`
- `stage_full_exit_code`
- `stage_full_duration_sec`
- `stage_remote_exit_code`
- `stage_remote_duration_sec`

이 구조면:

- 사람은 하위 marker와 상위 summary를 함께 읽을 수 있고
- 자동화는 상위 summary만 파싱해도 된다

## Error Handling

### Invalid stage selection

`--smoke-only`, `--full-only`, `--remote-only`를 동시에 여러 개 주면 실패시킨다.

이유:

- 의도를 모호하게 두지 않는다
- 추후 일반화 전까지는 표면을 단순하게 유지한다

### Subprocess failure

하위 스크립트가 non-zero exit code를 내면:

- 기본은 즉시 종료
- `--continue-on-failure`면 기록 후 계속 진행

### Missing python executable or bad path

suite는 실행 전 각 하위 스크립트 경로를 검증한다.

이렇게 하면 운영자가 이상한 에러 대신 명시적 실패를 본다.

## Relationship to Production Hub

이번 단계에서 suite는 `production hub operator entry`의 CLI 대응물로 본다.

즉 역할은 아래처럼 나뉜다.

- `/production`
  웹 기반 운영 허브
- `run_comic_verification_suite.py`
  터미널 기반 검증 허브

둘을 합치지 않는 이유는 책임 경계 때문이다.

- 웹 허브는 episode/work/series 중심 운영
- suite runner는 검증 orchestration 중심 운영

이 분리가 지금은 더 안전하다.

## Test Strategy

최소 회귀 범위는 아래다.

1. 기본 실행이 `smoke -> full -> remote` 순서를 사용한다
2. `--smoke-only`가 smoke만 실행한다
3. `--full-only`가 verification만 실행한다
4. `--remote-only`가 remote만 실행한다
5. 기본은 fail-fast다
6. `--continue-on-failure`는 다음 단계로 진행한다
7. summary marker가 기대한 값을 출력한다

실제 subprocess 실행은 테스트에서 monkeypatch로 대체한다.

## Success Criteria

이번 단계의 성공 기준은 아래와 같다.

1. 운영자가 단일 명령으로 comic verification suite를 실행할 수 있다.
2. 기본 실행 순서가 권장 순서를 따른다.
3. fail-fast와 continue-on-failure가 명확히 구분된다.
4. 특정 단계만 선택 실행할 수 있다.
5. suite 수준 summary가 별도로 출력된다.
