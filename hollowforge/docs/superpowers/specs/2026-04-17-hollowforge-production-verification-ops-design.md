# HollowForge Production Verification Ops Design

Date: 2026-04-17

## Goal

`/production`에 comic verification 운영 진입점을 명시적으로 노출한다.

이번 단계의 목표는 `/production`에서 검증을 직접 실행하는 것이 아니다.

- 운영자가 README, STATE, SOP를 뒤져 명령을 찾지 않아도 되게 한다.
- `/production`을 shared-core hub에서 운영 hub로 한 단계 더 밀어준다.
- comic verification suite를 표준 진입점으로 UI에 고정한다.

성공 기준은 아래 세 가지다.

1. 운영자는 `/production`에서 canonical verification 명령을 바로 확인할 수 있다.
2. 기본 경로가 `preflight -> suite runner` 순서로 명확히 드러난다.
3. isolated rerun 명령은 보조 수단으로만 노출되고 기본 경로보다 뒤에 배치된다.

## Current State

현재 HollowForge는 이미 아래를 갖고 있다.

- `/production`
  - shared production core creation + episode-aware resume hub
- `backend/scripts/check_comic_remote_render_preflight.py`
  - remote still lane preflight
- `backend/scripts/run_comic_verification_suite.py`
  - `smoke -> full -> remote` canonical verification suite
- README / STATE / SOP
  - 표준 운영 명령이 문서로는 정리돼 있음

즉 검증 계약은 이미 존재한다.

부족한 점은 이 계약이 UI 운영 허브에 아직 반영되지 않았다는 것이다.

## Problem Statement

문제는 기능 부족이 아니라 operator surface의 단절이다.

### 1. `/production`과 verification 운영 계약이 분리돼 있다

`/production`은 production episode 기준 허브가 되었지만, comic verification 자체는 여전히 문서나 터미널 기억에 의존한다.

### 2. 기본 경로와 보조 경로가 구분돼 보이지 않는다

현재 운영 표준은 분명하다.

1. `check_comic_remote_render_preflight.py`
2. `run_comic_verification_suite.py`
3. 필요하면 `--full-only` 또는 `--remote-only`

하지만 UI 상에는 이 우선순위가 없다.

### 3. episode row 액션으로 붙이면 의미가 왜곡된다

comic verification suite는 현재 구조상 특정 production episode 하나를 직접 받아 실행하는 도구가 아니다.

따라서 episode별 CTA로 붙이면 “이 episode만 검증한다”는 잘못된 기대를 만든다.

## Non-Goals

이번 단계에서 하지 않는 것:

- `/production`에서 shell command를 직접 실행하는 API 추가
- backend process launch / cancel / log streaming
- verification 결과 DB 저장
- episode별 verification history UI
- animation verification suite 추가
- `/production` row별 per-episode verification 버튼

## Considered Approaches

### 1. 문서 링크만 추가

`/production`에서 README나 SOP 링크만 제공한다.

장점:

- 구현이 가장 빠르다
- 안전하다

단점:

- 운영자가 결국 문서와 터미널을 다시 오가야 한다
- canonical command가 `/production` 표면에 직접 드러나지 않는다

운영 표준화 효과가 약하다.

### 2. 전역 Verification Ops 카드 추가

`/production` 상단에 전역 운영 카드 하나를 두고, copyable command와 SOP 링크를 노출한다.

장점:

- `/production`의 hub 역할과 맞다
- “기본 경로 vs isolated rerun” 우선순위를 UI에서 바로 설명할 수 있다
- 백엔드에서 임의 프로세스를 실행하지 않아도 된다
- 이후 자동화 API를 붙일 때도 operator contract를 재사용할 수 있다

단점:

- 여전히 실제 실행은 터미널에서 한다
- 복사 UI나 command presentation을 새로 설계해야 한다

현재 목표에 가장 적합하다.

### 3. `/production`에서 직접 실행

버튼 클릭으로 preflight/suite를 백엔드가 직접 실행하게 만든다.

장점:

- 자동화 수준이 가장 높다

단점:

- process management, logging, cancellation, permission boundary, concurrency 제어가 필요하다
- 현재 HollowForge 범위를 크게 넘는다

지금 단계에서는 과하다.

## Recommended Direction

권장 방향은 `전역 Verification Ops 카드`다.

위치는 `/production` 상단 hero 아래, creation forms 위가 적절하다.

이 위치의 장점은 다음과 같다.

- operator가 `/production`에 들어오자마자 canonical verification path를 본다
- shared core 생성과 verification 운영을 같은 허브 문맥에서 본다
- episode row 의미를 흐리지 않는다

## UI Contract

새 카드 이름은 `Verification Ops`로 둔다.

카드 안에는 아래 다섯 요소를 둔다.

1. `Run Preflight`
   - command text
2. `Run Comic Verification Suite`
   - command text
3. `Rerun Full Only`
   - command text
4. `Rerun Remote Only`
   - command text
5. `Open SOP`
   - comic operator SOP 문서 링크

실행 버튼이 아니라 “operator command surface”로 정의한다.

즉 카드의 책임은:

- canonical command 노출
- 기본 순서 설명
- fallback rerun 표면 제공

여기까지다.

## Command Contract

기본 표시 명령은 로컬 운영 기준으로 고정한다.

### Preflight

```bash
cd backend
./.venv/bin/python scripts/check_comic_remote_render_preflight.py \
  --backend-url http://127.0.0.1:8000
```

### Suite Runner

```bash
cd backend
./.venv/bin/python scripts/run_comic_verification_suite.py \
  --base-url http://127.0.0.1:8000
```

### Full Only

```bash
cd backend
./.venv/bin/python scripts/run_comic_verification_suite.py \
  --base-url http://127.0.0.1:8000 \
  --full-only
```

### Remote Only

```bash
cd backend
./.venv/bin/python scripts/run_comic_verification_suite.py \
  --base-url http://127.0.0.1:8000 \
  --remote-only
```

핵심은 isolated rerun도 기존 개별 helper가 아니라 suite runner flags 기준으로 보여주는 것이다.

이렇게 해야 operator contract가 하나로 고정된다.

## Interaction Model

카드는 명령을 눈으로 읽을 수 있어야 하고, 복사 동작이 있어야 한다.

최소 상호작용은 아래면 충분하다.

- command block
- `Copy Command` button
- copy 성공 toast

추가로 아래 짧은 설명을 둔다.

- 기본 경로:
  `Run Preflight` 다음에 `Run Comic Verification Suite`
- isolated rerun:
  suite가 실패 lane을 좁힌 뒤에만 사용

## Relationship To Episode Registry

episode registry row에는 verification CTA를 추가하지 않는다.

이유:

- suite는 per-episode tool이 아니다
- row CTA는 현재 `Open Comic Handoff` / `Open Animation Track` 의미만 유지하는 편이 명확하다
- verification는 hub-level ops로 유지해야 책임 경계가 맞다

## Test Strategy

최소 회귀 범위는 아래다.

1. `/production`에 `Verification Ops` heading이 보인다
2. preflight command가 보인다
3. suite runner command가 보인다
4. `--full-only`와 `--remote-only` rerun command가 보인다
5. SOP 링크가 올바른 문서 경로를 가리킨다
6. 기존 `Open Comic Handoff` / `Open Animation Track` row behavior는 그대로 유지된다

## Success Criteria

이번 단계의 성공 기준은 아래와 같다.

1. `/production` 상단에서 canonical comic verification path를 바로 볼 수 있다.
2. 운영자는 문서 검색 없이 preflight와 suite runner 명령을 복사할 수 있다.
3. isolated rerun은 보조 경로로만 보이고 기본 경로보다 약하게 배치된다.
4. episode row 행동 의미는 바뀌지 않는다.
