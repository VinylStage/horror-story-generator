# Task Scheduler System Design

> **Status:** IMPLEMENTED (Phase 3 Complete)
> **Application Version:** 2.0.3 <!-- x-release-please-version -->
> **Date:** 2026-01-18
> **Author:** Claude Code (with VinylStage)
> **Implementation:** `feat/88-scheduler-api-integration`

---

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0-2 | Core Scheduler Engine | ✅ Complete |
| Phase 3 | API Integration | ✅ Complete |
| Phase 4+ | Templates, Cron | 🔮 Planned |

### Phase 3 Implementation Summary

**New Files:**
- `src/api/_scheduler_state.py` - Singleton scheduler service management
- `src/api/schemas/scheduler.py` - Pydantic API schemas
- `src/api/routers/scheduler.py` - `/scheduler/*` endpoints

**Modified Files:**
- `src/api/main.py` - Lifespan + router registration
- `src/api/routers/tasks.py` - CRUD + task management
- `src/scheduler/service.py` - Status methods
- `src/scheduler/persistence.py` - Stats queries

---

## 1. Executive Summary

### 1.1 현재 상태 (As-Is)

```
┌─────────────────────────────────────────────────────────────┐
│  현재 API 구조                                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Direct APIs (동기, Blocking)                               │
│  ├── POST /research/run      → 완료까지 대기 (최대 300s)    │
│  └── POST /story/generate    → 완료까지 대기                │
│                                                             │
│  Task APIs (비동기, 즉시 실행) — REMOVED in v2.0.0           │
│  ├── POST /tasks/research/trigger   → (removed)              │
│  ├── POST /tasks/story/trigger      → (removed)              │
│  └── POST /tasks/batch/trigger      → (removed)              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**현재 문제점:**
- Task이 "스케줄링"이 아닌 "즉시 비동기 실행"
- 큐잉 없음 (모든 task이 병렬 실행)
- 우선순위 없음
- 리소스 경쟁 발생 가능 (Ollama 동시 접근)

### 1.2 목표 상태 (To-Be)

```
┌─────────────────────────────────────────────────────────────┐
│  목표 아키텍처                                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Direct API  │    │  Task Queue  │    │  Scheduler  │     │
│  │ (최고 우선) │    │  (FIFO+순서)│    │  (Worker)   │     │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘     │
│         │                  │                  │             │
│         └────────┬─────────┴─────────┬────────┘             │
│                  ▼                   ▼                      │
│         ┌────────────────────────────────────┐              │
│         │      Execution Engine              │              │
│         │  ┌──────────┐  ┌──────────┐       │              │
│         │  │ Worker 1 │  │ Worker 2 │  ...  │              │
│         │  └──────────┘  └──────────┘       │              │
│         └────────────────────────────────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 요구사항 정의

### 2.1 기능 요구사항 (Functional Requirements)

| ID | 요구사항 | 우선순위 | 상세 |
|----|----------|----------|------|
| FR-01 | Task 사전 등록 | P0 | 실행 전 미리 큐에 task 등록 가능 |
| FR-02 | 순서 변경 | P0 | 대기 중인 task의 실행 순서 조정 |
| FR-03 | 동시 실행 그룹 | P0 | 특정 task들을 묶어서 병렬 실행 |
| FR-04 | Direct API 최우선 | P0 | /story/generate, /research/run은 최고 우선순위 |
| FR-05 | 인터럽트 처리 | P0 | Direct 요청 시 현재 task 완료 후 Direct 먼저 실행 |
| FR-06 | Cron 스케줄링 | P1 | 반복 실행 설정 (예: 매일 오전 9시) |
| FR-07 | Task 상태 추적 | P0 | 큐 상태, 실행 상태, 완료 상태 조회 |
| FR-08 | Task 취소 | P1 | 대기 중 또는 실행 중 task 취소 |

### 2.2 비기능 요구사항 (Non-Functional Requirements)

| ID | 요구사항 | 상세 |
|----|----------|------|
| NFR-01 | 지속성 | 서버 재시작 후에도 큐 상태 유지 |
| NFR-02 | 원자성 | Task 상태 변경은 atomic하게 처리 |
| NFR-03 | 확장성 | Worker 수 동적 조정 가능 |
| NFR-04 | 모니터링 | 큐 상태, Worker 상태 실시간 조회 |

### 2.3 용어 정의

| 용어 | 정의 |
|------|------|
| **Task** | 실행 가능한 단일 작업 단위 (research 또는 story) |
| **Queue** | 실행 대기 중인 Task들의 순서 있는 목록 |
| **TaskGroup** | 동시에 실행될 Task들의 묶음 |
| **Direct Execution** | /story/generate, /research/run 통한 즉시 실행 |
| **Worker** | Task를 실제로 실행하는 프로세스/스레드 |
| **Scheduler** | Queue에서 Task를 꺼내 Worker에 할당하는 컴포넌트 |

---

## 3. 아키텍처 설계

### 3.1 컴포넌트 다이어그램

```
┌──────────────────────────────────────────────────────────────────┐
│                        API Layer                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐     │
│  │ Direct APIs    │  │ Queue APIs     │  │ Schedule APIs  │     │
│  │                │  │                │  │                │     │
│  │ POST /research │  │ POST /queue/   │  │ POST /schedule │     │
│  │      /run      │  │      add       │  │      /create   │     │
│  │ POST /story/   │  │ PUT  /queue/   │  │ GET  /schedule │     │
│  │      generate  │  │      reorder   │  │      /list     │     │
│  │                │  │ GET  /queue/   │  │ DELETE /sched. │     │
│  │                │  │      status    │  │      /{id}     │     │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘     │
│          │                   │                   │               │
└──────────┼───────────────────┼───────────────────┼───────────────┘
           │                   │                   │
           ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Scheduler Core                                │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Priority Queue  │  │ Group Manager   │  │ Cron Scheduler  │  │
│  │                 │  │                 │  │                 │  │
│  │ - Direct (P0)   │  │ - Group定義     │  │ - APScheduler   │  │
│  │ - Queued (P1)   │  │ - 동시실행 관리 │  │ - Cron 표현식   │  │
│  │ - Scheduled(P2) │  │                 │  │                 │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │            │
│           └──────────┬─────────┴──────────┬─────────┘            │
│                      ▼                    ▼                      │
│           ┌──────────────────────────────────────────┐           │
│           │           Execution Engine               │           │
│           │  ┌────────┐ ┌────────┐ ┌────────┐       │           │
│           │  │Worker 1│ │Worker 2│ │Worker N│       │           │
│           │  └────────┘ └────────┘ └────────┘       │           │
│           └──────────────────────────────────────────┘           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Storage Layer                                 │
├──────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Queue Storage   │  │ Task Storage     │  │ Schedule Store  │  │
│  │ (SQLite/Redis)  │  │ (JSON/SQLite)   │  │ (SQLite)        │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 실행 흐름 (Sequence)

#### 3.2.1 일반 Task 실행 흐름

```
Client          API            Scheduler         Worker          Storage
  │              │                │                │                │
  │──POST /queue/add──▶│         │                │                │
  │              │──save task──────────────────────────────────────▶│
  │              │◀─────────────────────────────────────────────────│
  │◀──202 Accepted──│            │                │                │
  │              │                │                │                │
  │              │     (Scheduler Loop)           │                │
  │              │                │──next task?────────────────────▶│
  │              │                │◀──────────────────────────────│
  │              │                │──dispatch────▶│                │
  │              │                │               │──execute───────▶
  │              │                │               │◀────────────────
  │              │                │◀──complete────│                │
  │              │                │──update status─────────────────▶│
```

#### 3.2.2 Direct API + 인터럽트 흐름

```
Client          API            Scheduler         Worker          Queue
  │              │                │                │                │
  │              │                │   [Task A 실행 중]               │
  │              │                │────────────────▶│               │
  │              │                │                │                │
  │──POST /story/generate─────────▶│               │                │
  │              │──mark priority──▶│              │                │
  │              │                │──wait A done──│                │
  │              │                │◀──A complete──│                │
  │              │                │                │                │
  │              │                │──execute Direct─▶│             │
  │              │                │◀──Direct done──│               │
  │◀──200 OK + result──────────────│              │                │
  │              │                │                │                │
  │              │                │──resume queue──────────────────▶│
  │              │                │──next task (B)─▶│               │
```

### 3.3 상태 다이어그램

```
                    ┌─────────────────────────────────────────┐
                    │              Task States                  │
                    └─────────────────────────────────────────┘

    ┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
    │ PENDING │─────▶│ QUEUED  │─────▶│ RUNNING │─────▶│COMPLETED│
    └─────────┘      └─────────┘      └─────────┘      └─────────┘
         │                │                │                │
         │                │                │                ▼
         │                │                │          ┌─────────┐
         │                ▼                ▼          │ SUCCESS │
         │          ┌─────────┐      ┌─────────┐      ├─────────┤
         └─────────▶│CANCELLED│◀─────│ FAILED  │      │ FAILED  │
                    └─────────┘      └─────────┘      ├─────────┤
                                                      │ SKIPPED │
                                                      └─────────┘

    상태 전이:
    - PENDING: 생성됨, 아직 큐에 추가되지 않음 (예약된 task)
    - QUEUED: 큐에 추가됨, 실행 대기 중
    - RUNNING: 현재 실행 중
    - COMPLETED: 실행 완료 (SUCCESS/FAILED/SKIPPED)
    - CANCELLED: 사용자에 의해 취소됨
```

---

## 4. 데이터 모델

### 4.1 Task Model

```python
@dataclass
class Task:
    # Identity
    task_id: str                    # UUID, 예: "task-550e8400-e29b-41d4-a716-446655440000"
    task_type: TaskType              # RESEARCH | STORY

    # Execution parameters
    params: Dict[str, Any]         # 실행에 필요한 파라미터

    # Scheduling
    priority: Priority             # DIRECT(0) | HIGH(1) | NORMAL(2) | LOW(3)
    group_id: Optional[str]        # 동시 실행 그룹 ID
    position: Optional[int]        # 큐 내 순서 (reorder용)

    # Status
    status: TaskStatus              # PENDING | QUEUED | RUNNING | COMPLETED | CANCELLED
    result: Optional[TaskResult]    # SUCCESS | FAILED | SKIPPED

    # Timestamps
    created_at: datetime
    queued_at: Optional[datetime]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    # Execution info
    worker_id: Optional[str]
    pid: Optional[int]
    log_path: Optional[str]
    artifacts: List[str]           # 생성된 파일 경로들

    # Error handling
    error: Optional[str]
    retry_count: int = 0
    max_retries: int = 0

    # Webhook
    webhook_url: Optional[str]
    webhook_events: List[str]      # ["succeeded", "failed", "skipped"]
    webhook_sent: bool = False

class TaskType(Enum):
    RESEARCH = "research"
    STORY = "story"

class Priority(Enum):
    DIRECT = 0    # 최고 우선순위 (Direct API)
    HIGH = 1
    NORMAL = 2    # 기본값
    LOW = 3

class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class TaskResult(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
```

### 4.2 Group Model (동시 실행 그룹)

```python
@dataclass
class TaskGroup:
    group_id: str                  # UUID, 예: "group-550e8400..."
    name: Optional[str]            # 사람이 읽기 쉬운 이름
    task_ids: List[str]             # 그룹에 속한 task들

    # Execution mode
    mode: GroupMode                # PARALLEL | SEQUENTIAL

    # Status (집계)
    status: GroupStatus            # PENDING | RUNNING | COMPLETED | PARTIAL

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    # Summary
    total_tasks: int
    completed_tasks: int
    succeeded_tasks: int
    failed_tasks: int

class GroupMode(Enum):
    PARALLEL = "parallel"          # 그룹 내 task들을 동시 실행
    SEQUENTIAL = "sequential"      # 그룹 내 task들을 순차 실행
```

### 4.3 Schedule Model (Cron 스케줄)

```python
@dataclass
class Schedule:
    schedule_id: str               # UUID
    name: str                      # 스케줄 이름

    # Task template
    task_type: TaskType
    task_params: Dict[str, Any]

    # Cron expression
    cron_expression: str           # "0 9 * * *" (매일 오전 9시)
    timezone: str = "Asia/Seoul"

    # Control
    enabled: bool = True

    # Execution history
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    run_count: int = 0

    # Timestamps
    created_at: datetime
    updated_at: datetime
```

### 4.4 Queue State

```python
@dataclass
class QueueState:
    # Current execution
    running_tasks: List[str]        # 현재 실행 중인 task_ids
    running_groups: List[str]      # 현재 실행 중인 group_ids

    # Waiting
    queued_tasks: List[str]         # 대기 중인 task_ids (순서대로)

    # Direct execution waiting
    pending_direct: List[str]      # Direct API로 요청된 대기 중인 task_ids

    # Statistics
    total_queued: int
    total_running: int
    total_completed_today: int
```

---

## 5. API 설계

### 5.1 Queue Management APIs

#### 5.1.1 Add Task to Queue

```http
POST /queue/tasks
Content-Type: application/json

{
  "task_type": "research",          # "research" | "story"
  "params": {
    "topic": "Korean apartment horror",
    "tags": ["urban", "isolation"],
    "model": "qwen3:30b"
  },
  "priority": "normal",            # "high" | "normal" | "low" (default: normal)
  "group_id": null,                # Optional: 기존 그룹에 추가
  "position": null                 # Optional: 특정 위치에 삽입 (0-based)
}

Response: 201 Created
{
  "task_id": "task-550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "position": 3,
  "estimated_wait": "PT15M"        # ISO 8601 duration
}
```

#### 5.1.2 Create Task Group

```http
POST /queue/groups
Content-Type: application/json

{
  "name": "Daily Horror Research Batch",
  "mode": "parallel",              # "parallel" | "sequential"
  "tasks": [
    {
      "task_type": "research",
      "params": { "topic": "Topic 1" }
    },
    {
      "task_type": "research",
      "params": { "topic": "Topic 2" }
    }
  ]
}

Response: 201 Created
{
  "group_id": "group-550e8400...",
  "task_ids": ["task-1", "task-2"],
  "status": "queued",
  "position": 5
}
```

#### 5.1.3 Reorder Queue

```http
PUT /queue/reorder
Content-Type: application/json

{
  "task_id": "task-550e8400...",
  "new_position": 0                # 맨 앞으로 이동
}

Response: 200 OK
{
  "task_id": "task-550e8400...",
  "old_position": 5,
  "new_position": 0
}
```

```http
PUT /queue/reorder/bulk
Content-Type: application/json

{
  "order": [
    "task-3",
    "task-1",
    "task-2"
  ]
}

Response: 200 OK
{
  "reordered": 3
}
```

#### 5.1.4 Get Queue Status

```http
GET /queue/status

Response: 200 OK
{
  "running": {
    "tasks": [
      {
        "task_id": "task-current",
        "task_type": "story",
        "started_at": "2026-01-18T10:00:00Z",
        "progress": "generating"
      }
    ],
    "groups": []
  },
  "queued": {
    "total": 5,
    "tasks": [
      { "task_id": "task-1", "position": 0, "task_type": "research" },
      { "task_id": "task-2", "position": 1, "task_type": "story" }
    ]
  },
  "pending_direct": [],
  "statistics": {
    "completed_today": 12,
    "failed_today": 1,
    "avg_wait_time": "PT8M30S"
  }
}
```

#### 5.1.5 Cancel Task

```http
DELETE /queue/tasks/{task_id}

Response: 200 OK
{
  "task_id": "task-550e8400...",
  "previous_status": "queued",
  "new_status": "cancelled"
}
```

### 5.2 Schedule Management APIs

#### 5.2.1 Create Schedule

```http
POST /schedules
Content-Type: application/json

{
  "name": "Daily Morning Research",
  "task_type": "research",
  "task_params": {
    "topic": "Daily horror trends",
    "tags": ["daily", "trends"]
  },
  "cron_expression": "0 9 * * *",  # 매일 오전 9시
  "timezone": "Asia/Seoul",
  "enabled": true
}

Response: 201 Created
{
  "schedule_id": "sched-550e8400...",
  "name": "Daily Morning Research",
  "next_run_at": "2026-01-19T09:00:00+09:00"
}
```

#### 5.2.2 List Schedules

```http
GET /schedules

Response: 200 OK
{
  "schedules": [
    {
      "schedule_id": "sched-1",
      "name": "Daily Morning Research",
      "cron_expression": "0 9 * * *",
      "enabled": true,
      "last_run_at": "2026-01-18T09:00:00+09:00",
      "next_run_at": "2026-01-19T09:00:00+09:00"
    }
  ],
  "total": 1
}
```

#### 5.2.3 Update Schedule

```http
PUT /schedules/{schedule_id}
Content-Type: application/json

{
  "enabled": false
}

Response: 200 OK
{
  "schedule_id": "sched-1",
  "enabled": false,
  "next_run_at": null
}
```

### 5.3 Direct Execution APIs (기존 유지, 우선순위 추가)

```http
POST /story/generate
Content-Type: application/json

{
  "topic": "optional topic"
}

# 내부 동작:
# 1. Priority.DIRECT로 표시
# 2. 현재 실행 중인 task 완료 대기
# 3. 대기 중인 queue보다 먼저 실행
# 4. 완료 후 결과 반환

Response: 200 OK
{
  "success": true,
  "story": "...",
  "interrupted_tasks": ["task-1"]    # NEW: 인터럽트된 task 정보
}
```

---

## 6. 구현 고려사항

### 6.1 Storage 선택

| Option | 장점 | 단점 | 권장 |
|--------|------|------|------|
| **SQLite** | 단순, 파일 기반, 트랜잭션 | 동시성 제한 | ✅ 단일 서버 |
| **Redis** | 빠름, Pub/Sub, TTL | 별도 서버 필요 | 분산 환경 |
| **JSON Files** | 현재 구조 유지 | Lock 관리 복잡 | ❌ |

**권장:** SQLite (단일 서버 환경, 현재 프로젝트 규모에 적합)

### 6.2 Scheduler 구현

| Option | 장점 | 단점 | 권장 |
|--------|------|------|------|
| **APScheduler** | Python 네이티브, Cron 지원 | 메모리 기반 | ✅ |
| **Celery** | 분산, 강력한 기능 | 복잡, Redis/RabbitMQ 필요 | 대규모 |
| **Custom** | 완전한 제어 | 구현 비용 | ❌ |

**권장:** APScheduler + SQLite TaskStore

### 6.3 Worker 모델

```python
# Option A: Thread Pool
class ThreadPoolWorker:
    def __init__(self, max_workers=2):
        self.executor = ThreadPoolExecutor(max_workers)

# Option B: Process Pool
class ProcessPoolWorker:
    def __init__(self, max_workers=2):
        self.executor = ProcessPoolExecutor(max_workers)

# Option C: Async (현재 방식 개선)
class AsyncWorker:
    async def execute(self, task: Task):
        result = run_task_in_process(task)
```

**권장:** Option C (Async) - 현재 구조와 일관성 유지

### 6.4 동시성 제어

```python
class ConcurrencyManager:
    def __init__(self):
        self.running_lock = asyncio.Lock()
        self.direct_event = asyncio.Event()

    async def can_start_task(self, task: Task) -> bool:
        """Direct 요청이 대기 중이면 일반 task 시작 불가"""
        if task.priority != Priority.DIRECT:
            if self.direct_event.is_set():
                return False
        return True

    async def wait_for_current_task(self):
        """현재 실행 중인 task 완료 대기"""
        async with self.running_lock:
            pass
```

---

## 7. 엣지 케이스 및 고려사항

### 7.1 Direct API 인터럽트 시나리오

```
시나리오: Task A 실행 중 + Direct 요청 도착

Timeline:
T0: Task A 시작
T1: Direct 요청 도착
T2: Task A 완료
T3: Direct 실행 시작
T4: Direct 완료
T5: Queue의 다음 Task 시작

질문:
Q1: Task A가 매우 오래 걸리면? (예: 10분)
    → 옵션 A: Direct는 무조건 대기
    → 옵션 B: Timeout 설정 후 강제 실행
    → 옵션 C: Task A를 graceful하게 중단

Q2: Direct 요청이 연속으로 여러 개 오면?
    → FIFO로 처리 (먼저 온 Direct 먼저)
```

### 7.2 Group 실행 시나리오

```
시나리오: Group G (Task A, B, C를 parallel)가 실행 중 + Direct 요청

질문:
Q3: Group 전체 완료를 기다릴 것인가, 개별 Task 완료 후 인터럽트?
    → 옵션 A: Group 전체 완료 후 Direct
    → 옵션 B: 하나라도 완료되면 Direct 먼저
```

### 7.3 서버 재시작 시나리오

```
시나리오: 서버 재시작 시 running 상태인 task이 있음

처리 방안:
1. RUNNING → FAILED (error: "interrupted by server restart")
2. 자동 재시작 옵션 제공 (retry_on_restart: true)
3. 큐 상태는 보존
```

### 7.4 Ollama 리소스 충돌

```
시나리오: Story task과 Research task이 동시에 Ollama 접근

현재 문제: 둘 다 qwen3:30b 사용 시 메모리 부족

해결 방안:
1. 같은 모델 사용하는 task은 sequential로 강제
2. Resource Lock 추가
3. Worker 수를 1로 제한 (가장 간단)
```

---

## 8. 협의 필요 사항

### 8.1 결정 필요 (Decision Required)

| ID | 항목 | 옵션 | 권장 |
|----|------|------|------|
| D-01 | Storage 선택 | SQLite / Redis / JSON | SQLite |
| D-02 | Scheduler 라이브러리 | APScheduler / Celery / Custom | APScheduler |
| D-03 | Direct 인터럽트 대기 시간 | 무제한 / Timeout (N초) | Timeout 300s |
| D-04 | Group 인터럽트 정책 | 전체 대기 / 개별 즉시 | 전체 대기 |
| D-05 | 기본 Worker 수 | 1 / 2 / N | 1 (리소스 안전) |

### 8.2 추가 논의 필요 (Discussion Required)

| ID | 항목 | 질문 |
|----|------|------|
| Q-01 | 기존 API 호환성 | **Resolved (v2.0.0):** Legacy `/tasks/*` endpoints removed. `POST /tasks` is the sole task creation API. |
| Q-02 | Batch API | **Resolved (v2.0.0):** Legacy batch trigger removed. Use `POST /tasks` with array input for batch creation. |
| Q-03 | Webhook 통합 | 기존 webhook 로직 재사용 or 새로 구현? |
| Q-04 | UI/Dashboard | 큐 관리 UI 필요 여부 |
| Q-05 | 테스트 전략 | 스케줄러 테스트 방법 (시간 mocking 등) |

### 8.3 확인 필요 (Confirmation Required)

| ID | 항목 | 현재 이해 | 확인 |
|----|------|----------|------|
| C-01 | Direct 우선순위 | /story/generate, /research/run 모두 최고 우선 | ☐ |
| C-02 | Group 모드 | parallel만? sequential도? | ☐ |
| C-03 | 순서 변경 대상 | QUEUED 상태만? PENDING도? | ☐ |
| C-04 | Cron 시간대 | Asia/Seoul 기본? 설정 가능? | ☐ |

---

## 9. 구현 로드맵

### Phase 0-2: Core Scheduler Engine ✅ COMPLETE
- [x] SQLite 기반 Task/Queue storage 구현
- [x] Priority Queue 로직 구현
- [x] Dispatcher 및 Executor
- [x] TaskGroup sequential execution
- [x] Crash recovery

### Phase 3: API Integration ✅ COMPLETE
- [x] `/scheduler/*` Control APIs (start, stop, status)
- [x] `/tasks` CRUD APIs
- [x] `/tasks/{id}/runs` 실행 이력 조회
- [x] Legacy trigger endpoints removed (v2.0.0)
- [x] CumulativeStats 통계 제공
- [x] Singleton SchedulerService 관리

### Phase 4: Templates & Scheduling (Planned)
- [ ] TaskTemplate CRUD APIs
- [ ] Cron Schedule APIs
- [ ] APScheduler 통합

### Phase 5: Monitoring & Polish (Planned)
- [ ] `/scheduler/metrics` 상세 통계
- [ ] Webhook 통합
- [ ] UI Dashboard 연동

---

## 10. 참고 자료

- Task Scheduler 구현: `src/scheduler/`
- Task API: `src/api/routers/tasks.py`
- Webhook: `src/infra/webhook.py`
- APScheduler 문서: https://apscheduler.readthedocs.io/
- SQLite 동시성: https://www.sqlite.org/lockingv3.html

---

## Appendix A: 현재 코드 위치 참조

| 컴포넌트 | 파일 |
|----------|------|
| Task Scheduler | `src/scheduler/` |
| Task API | `src/api/routers/tasks.py` |
| Scheduler API | `src/api/routers/scheduler.py` |
| Research Direct | `src/api/routers/research.py` |
| Story Direct | `src/api/routers/story.py` |
| Webhook | `src/infra/webhook.py` |
