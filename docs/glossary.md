# Glossary (용어 사전)

**Application Version:** 1.7.0 <!-- x-release-please-version -->
**Last Updated:** 2026-02-09

---

## 현재 용어 (v1.7.0+)

| 용어 | 설명 |
|------|------|
| **Task** | 수행할 작업의 정의. 스케줄러에 의해 큐잉 및 실행됨 |
| **TaskRun** | Task의 단일 실행 기록. 1:1 관계 (DEC-001) |
| **TaskGroup** | 여러 Task를 그룹화하여 순차/병렬 실행 |
| **TaskTemplate** | Task 생성을 위한 템플릿 (재사용 가능한 파라미터 세트) |
| **Schedule** | 반복 실행을 위한 cron 기반 스케줄 정의 |
| **Scheduler** | Task를 TaskRun으로 변환하는 백그라운드 실행 엔진 |
| **Dispatcher** | 큐에서 다음 Task를 가져와 실행기에 전달하는 컴포넌트 |
| **QueueManager** | Task 큐 관리 (우선순위, 순서, CRUD) |
| **Direct Execution** | `/story/generate`, `/research/run` 등 동기 API 호출에 의한 즉시 실행 |
| **Research Card** | 연구 조사 결과를 구조화한 JSON 파일 |
| **Story Registry** | 생성된 스토리의 메타데이터를 관리하는 SQLite DB |
| **Canonical Key** | 연구 카드의 정규화된 분류 키 |

---

## 폐기된 용어

| 이전 용어 | 현재 용어 | 폐기 시점 | 비고 |
|----------|----------|----------|------|
| Job | **Task** | v1.7.0 | 코드 및 API에서 완전 대체 |
| JobRun | **TaskRun** | v1.7.0 | |
| JobGroup | **TaskGroup** | v1.7.0 | |
| `/jobs/*` 엔드포인트 | **`/tasks/*`** | v1.7.0 (API), v2.0.0 (제거) | PR #139에서 레거시 엔드포인트 완전 제거 |
| `/jobs/story/trigger` | **`/story/generate`** | v1.7.0 (제거) | Direct execution으로 대체 |
| `/jobs/research/trigger` | **`/research/run`** | v1.7.0 (제거) | Direct execution으로 대체 |
| `main.py` CLI | **(제거됨)** | v2.0.0 | API 전용으로 전환 (PR #139) |
| `job_manager.py` | **(제거됨)** | v2.0.0 | Scheduler 서비스로 대체 |
| `job_monitor.py` | **(제거됨)** | v2.0.0 | Scheduler 서비스로 대체 |
| `succeeded` (상태) | **COMPLETED** | v1.7.0 | DEC-006 통합 상태 모델 |
| `error` (상태) | **FAILED** | v1.7.0 | DEC-006 |
| `dispatched` (상태) | **(내부 전용)** | v1.7.0 | 외부 노출하지 않음 |
| `JOB_DIR` (환경변수) | **(제거됨)** | v2.0.0 | SQLite 기반 스토리지로 전환 |

---

## 상태 모델

### Task Status (큐 레벨)

| 상태 | 의미 |
|------|------|
| `QUEUED` | 큐에서 대기 중 |
| `RUNNING` | 현재 실행 중 |
| `CANCELLED` | 완료 전 취소됨 |

### TaskRun Status (실행 결과)

| 상태 | 의미 |
|------|------|
| `COMPLETED` | 성공적으로 완료 |
| `FAILED` | 오류 발생 |
| `SKIPPED` | 의도적으로 건너뜀 |

---

## 참고 문서

- [DOMAIN_MODEL.md](task-scheduler/DOMAIN_MODEL.md) - 도메인 모델 정의
- [API_CONTRACT.md](task-scheduler/API_CONTRACT.md) - API 계약
- [DESIGN_GUARDS.md](task-scheduler/DESIGN_GUARDS.md) - 설계 가드레일 (DEC-006)
