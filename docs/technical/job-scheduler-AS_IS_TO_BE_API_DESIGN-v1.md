# As-Is / To-Be API 아키텍처 설계

> **Status:** IMPLEMENTED (Phase 3 Complete)
> **Document Version:** 1.1.0
> **Application Version:** 1.5.0
> **Last Updated:** 2026-01-18
> **Implementation Commit:** feat/88-scheduler-api-integration

## 1. 목적
본 문서는 현재(As-Is) API 아키텍처와 목표(To-Be) 아키텍처를 명확히 구분하여 설명하고,
기존 엔드포인트를 유지하면서 Scheduler 기반 실행 모델로 전환하기 위한 설계 기준을 정리한다.

---

## 2. As-Is 아키텍처 (이전 상태)

### 2.1 핵심 특징
- API는 CLI 실행을 트리거하는 얇은 레이어 역할을 수행한다
- 실제 비즈니스 로직은 CLI 엔트리포인트에 존재한다
- 영속적인 Job 리소스가 존재하지 않는다
- 큐 또는 스케줄러 개념이 없다

### 2.2 실행 모델
1. 클라이언트가 trigger API를 호출한다
2. API 서버가 subprocess 형태로 CLI를 실행한다
3. 프로세스는 즉시 실행된다
4. API는 PID 및 실행 상태만을 추적한다

### 2.3 기존 엔드포인트 (요약)
- POST /jobs/story/trigger
- POST /jobs/research/trigger
- GET  /jobs/{job_id}
- POST /jobs/{job_id}/cancel

### 2.4 한계점
- 지연 실행(Deferred execution)이 불가능하다
- 배치 또는 다중 작업 관리가 어렵다
- 스케줄러의 생명주기를 제어할 수 없다
- "예정된 작업" 중심의 UI를 구성하기 어렵다

---

## 3. To-Be 아키텍처 (현재 상태 - IMPLEMENTED)

### 3.1 핵심 원칙
- Job은 영속적인 도메인 리소스이다
- Scheduler가 실행 시점을 통제한다
- API는 단일 제어 플레인(Single Control Plane)이다
- 실행은 요청 시점과 분리된다
- time에 대한 명시가 없을 경우(null),
  해당 Job은 즉시 실행 대상로 간주되며
  스케줄러가 동작 중이라면 즉시 실행 큐에 포함된다.


### 3.2 도메인 개념
- Job: 수행할 작업의 정의
- JobRun: Job의 단일 실행 시도
- Scheduler: Job을 JobRun으로 변환하는 백그라운드 실행 엔진

---

## 4. To-Be API 구조

### 4.1 Job 관리 (CRUD)
- POST   /jobs
  - 기존 api 와 다르게 엔드포인트에 story, research 구분을 짓지 않고 body 안의 type으로 구분한다.
- GET    /jobs
  - Job 목록 조회
- GET    /jobs/{job_id}
  - 특정 JOB 상세 조회
- PATCH  /jobs/{job_id}
  - 특정 JOB 업데이트
  - PATCH는 Job의 메타데이터 또는 실행 순서 관련 필드 변경을 위해 사용되며,
    실행 순서 전체를 재정렬하는 기능은 초기 범위에 포함하지 않는다.
  - **Phase 3 구현 범위**: priority 변경만 지원
- DELETE /jobs/{job_id}
  - **Phase 3 구현 범위**: QUEUED 상태 Job만 삭제 가능

### 4.2 Scheduler 제어 (독립 시스템 리소스)

> **Design Note**: Scheduler는 Job의 하위 리소스가 아닌 **독립적인 시스템 제어 플레인**으로 설계되었습니다.
> 이는 라우터 경로 충돌을 방지하고, 향후 `/scheduler/config`, `/scheduler/metrics` 등
> 확장을 용이하게 합니다.

- POST /scheduler/start: 스케줄러 시작 (idempotent)
- POST /scheduler/stop: 스케줄러 중지 (진행하던 작업은 즉시중지가 아니라 graceful 하게 중지)
- GET  /scheduler/status
  - 스케줄러 실행 여부 (`scheduler_running`)
  - 현재 실행 중인 Job ID (`current_job_id`, nullable)
  - 현재 대기 중인 Job 큐 길이 (`queue_length`)
  - 누적 처리 통계 (`cumulative_stats`)
    - `total_executed`: 총 실행된 JobRun 수
    - `succeeded`: COMPLETED 상태 JobRun 수
    - `failed`: FAILED 상태 JobRun 수
    - `cancelled`: CANCELLED 상태 Job 수
    - `skipped`: SKIPPED 상태 JobRun 수
  - Direct API 예약 상태 (`has_active_reservation`)

### 4.3 실행 관찰
- GET /jobs/{job_id}/runs
  - Job에 대한 실행 이력 (JobRun) 조회
  - 1:1 관계 (각 Job당 최대 1개 JobRun)

---

## 5. 기존 엔드포인트 유지 전략

### 5.1 호환(Compatibility) 모드
기존 trigger 엔드포인트는 즉시 제거하지 않고 유지하되,
**deprecated**로 표시된다.

- POST /jobs/story/trigger [DEPRECATED]
- POST /jobs/research/trigger [DEPRECATED]

현재 동작:
- 기존 subprocess 방식 유지 (backward compatibility)
- 신규 클라이언트는 `/jobs` API 사용 권장

### 5.2 Deprecated 정책
- 해당 엔드포인트들은 OpenAPI에서 deprecated로 표시
- 즉각적인 제거는 하지 않는다
- UI 및 신규 클라이언트는 /jobs 기반 API만 사용한다

---

## 6. 마이그레이션 단계

### Phase 0 (완료)
- Scheduler 구현 완료
- API에는 아직 직접 노출되지 않음
- CLI-trigger 모델 유지

### Phase 1 (현재 - IMPLEMENTED)
- /jobs CRUD API 도입 ✅
- /scheduler 제어 API 도입 ✅ (독립 루트로 변경)
- 기존 trigger 엔드포인트 deprecated 마킹 ✅

### Phase 2 (다음)
- UI는 /jobs API만을 기준으로 동작
- legacy 엔드포인트 내부 매핑을 scheduler로 전환

### Phase 3 (향후)
- CLI trigger 엔드포인트 제거 (별도 의사결정 필요)

---

## 7. 비목표(Non-Goals)
- 분산 워커 구조
- 멀티 테넌트 스케줄링
- 외부 크론 시스템 연동
- Redis 기반 스토리지 (현재 SQLite 유지)

---

## 8. 요약
본 전환 설계는 운영 안정성을 유지하면서,
Scheduler 기반 실행 모델과 향후 UI 확장을 가능하게 하는 것을 목표로 한다.

---

## 변경 이력

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-18 | 초기 설계 문서 |
| 1.1.0 | 2026-01-18 | Phase 3 구현 완료 반영. Scheduler 경로 `/scheduler/*`로 변경 |
