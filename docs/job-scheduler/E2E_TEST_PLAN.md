# Job Scheduler End-to-End Test Plan

**Document Version:** 1.0.0
**Application Version:** 1.5.0 (managed by release-please - DO NOT CHANGE)
**Phase:** 6-A Merge Validation
**Last Updated:** 2026-01-18

---

## 1. Purpose

This document defines the End-to-End (E2E) test plan for the Job Scheduler.
E2E tests validate the complete scheduler lifecycle with all components
integrated, ensuring the system behaves correctly as a whole.

### 1.1 Scope

| Category | In Scope | Out of Scope |
|----------|----------|--------------|
| Scheduler E2E | Job lifecycle, dispatch, retry, recovery, JobGroup | UI testing |
| Pipeline E2E | Real story/research execution | Performance benchmarks |
| Integration | Component interaction, callbacks | External webhook delivery |

### 1.2 Test Categories

1. **Scheduler E2E (test_e2e.py)** - Tests scheduler mechanics with mock handlers
2. **Pipeline E2E (optional)** - Tests real data generation pipelines

---

## 2. Environment

### 2.1 Test Database

- SQLite in-memory or temporary file
- Fresh database per test (isolation)
- WAL mode enabled for crash recovery tests

### 2.2 Resource Usage Policy

**CRITICAL: Resource constraints for local Ollama usage**

| Rule | Description |
|------|-------------|
| RULE-1 | Only ONE local Ollama workload may run at any time |
| RULE-2 | All concurrent workloads MUST use external APIs |
| RULE-3 | API cost usage approved for test purposes |
| RULE-4 | Tests document which resource type is used |

### 2.3 Test Components

```
┌─────────────────────────────────────────────────────────┐
│                   E2E Test Harness                      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────┐   │
│  │              SchedulerService                    │   │
│  │  ┌──────────┬──────────┬──────────┬──────────┐  │   │
│  │  │Dispatcher│ Executor │  Queue   │ Recovery │  │   │
│  │  │          │          │ Manager  │ Manager  │  │   │
│  │  └──────────┴──────────┴──────────┴──────────┘  │   │
│  └─────────────────────────────────────────────────┘   │
│                        │                                │
│  ┌─────────────────────▼───────────────────────────┐   │
│  │           E2EJobHandler (Mock)                   │   │
│  │  - Configurable results                          │   │
│  │  - Execution tracking                            │   │
│  │  - Failure injection                             │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Scheduler E2E Test Scenarios

### 3.1 E2E-NORM: Normal Queue Execution

| Test ID | Description | Steps | Expected |
|---------|-------------|-------|----------|
| E2E-NORM-01 | Single job lifecycle | Enqueue → Dispatch → Execute | COMPLETED |
| E2E-NORM-02 | Priority ordering | Enqueue 3 jobs with different priorities | Execute in priority order |
| E2E-NORM-03 | Job cancellation | Enqueue → Cancel before dispatch | CANCELLED, no execution |

### 3.2 E2E-DIRECT: Direct API Reservation (DEC-004)

| Test ID | Description | Steps | Expected |
|---------|-------------|-------|----------|
| E2E-DIRECT-01 | Empty queue immediate | Direct on empty queue | Executes immediately |
| E2E-DIRECT-02 | Between queued jobs | Job1 → Direct → Job2 | Order preserved |
| E2E-DIRECT-03 | Queue pauses | Create reservation → Dispatch | Queue paused |

### 3.3 E2E-RETRY: Retry Flow (DEC-007)

| Test ID | Description | Steps | Expected |
|---------|-------------|-------|----------|
| E2E-RETRY-01 | Single failure retry | Job fails once | Retry created |
| E2E-RETRY-02 | Max 3 attempts | Job fails repeatedly | 4 total attempts (1+3) |
| E2E-RETRY-03 | Retry chain linkage | Multiple failures | retry_of chain preserved |

### 3.4 E2E-RECOVERY: Crash Recovery

| Test ID | Description | Steps | Expected |
|---------|-------------|-------|----------|
| E2E-RECOVERY-01 | Running job recovery | Simulate crash during RUNNING | FAILED JobRun created |
| E2E-RECOVERY-02 | Retry for recovered | Recovery + retry evaluation | Retry job created |

### 3.5 E2E-GROUP: JobGroup Sequential Execution (DEC-012)

| Test ID | Description | Steps | Expected |
|---------|-------------|-------|----------|
| E2E-GROUP-01 | Sequential execution | 3 jobs in group | Execute in sequence order |
| E2E-GROUP-02 | Stop-on-failure | Job 2 fails (all retries) | Job 3 SKIPPED, group PARTIAL |
| E2E-GROUP-03 | Completed group | All jobs succeed | Group COMPLETED |

### 3.6 E2E-WEBHOOK: Webhook Emission

| Test ID | Description | Steps | Expected |
|---------|-------------|-------|----------|
| E2E-WEBHOOK-01 | Completed schema | Job completes | event: job.run.completed |
| E2E-WEBHOOK-02 | Failed includes error | Job fails | error field populated |
| E2E-WEBHOOK-03 | Skipped for group | Stop-on-failure | event: job.run.skipped |
| E2E-WEBHOOK-04 | At-least-once | Semantic validation | run_id as idempotency key |

---

## 4. Pipeline E2E Test Scenarios (Optional)

**Note:** These tests require actual API keys or local Ollama setup.
They validate real data generation pipelines.

### 4.1 PIPE-01: Story Generation via External API

| Step | Action | Expected |
|------|--------|----------|
| 1 | Create story job with external API model | Job QUEUED |
| 2 | Execute job | RUNNING state |
| 3 | Wait for completion | COMPLETED state |
| 4 | Verify artifacts | Story output file exists |
| 5 | Verify logs | Execution log preserved |

**Resource:** External API (NOT local Ollama)

### 4.2 PIPE-02: Research Generation via Local Ollama

| Step | Action | Expected |
|------|--------|----------|
| 1 | Create research job with Ollama model | Job QUEUED |
| 2 | Execute job | RUNNING state |
| 3 | Verify single Ollama usage | No concurrent Ollama jobs |
| 4 | Wait for completion | COMPLETED state |
| 5 | Verify artifacts | Research card created |

**Resource:** Local Ollama (EXCLUSIVE)

### 4.3 PIPE-03: Mixed Load Resource Constraint

| Step | Action | Expected |
|------|--------|----------|
| 1 | Start Ollama job | RUNNING state |
| 2 | Enqueue API job | QUEUED state |
| 3 | Verify no concurrent Ollama | Only one Ollama workload |
| 4 | Complete Ollama job | COMPLETED |
| 5 | API job executes | RUNNING → COMPLETED |

**Resource:** Ollama (exclusive) + External API (concurrent OK)

### 4.4 PIPE-04: Real Pipeline Failure + Retry

| Step | Action | Expected |
|------|--------|----------|
| 1 | Create job with invalid params | Job QUEUED |
| 2 | Execute → Fail | FAILED state |
| 3 | Verify auto-retry | Up to 3 retries |
| 4 | All attempts fail | Final FAILED state |
| 5 | Verify logs | All execution logs preserved |

### 4.5 PIPE-05: Crash During Real Execution

| Step | Action | Expected |
|------|--------|----------|
| 1 | Start real generation job | RUNNING state |
| 2 | Kill scheduler process | Process terminated |
| 3 | Restart scheduler | Recovery runs |
| 4 | Verify recovery | FAILED JobRun with error |
| 5 | Verify retry/cancel | Follows design rules |

---

## 5. Success/Failure Criteria

### 5.1 Pass Criteria

| Category | Requirement |
|----------|-------------|
| Scheduler E2E | All 18 tests pass |
| Pipeline E2E | All applicable tests pass (environment-dependent) |
| Regression | No existing tests fail |
| Resource | No Ollama resource violations |

### 5.2 Failure Criteria

| Condition | Action |
|-----------|--------|
| Any E2E test fails | Investigate, fix, re-test |
| Existing test regresses | Block merge until resolved |
| Resource constraint violated | Block merge, fix design |
| Recovery test fails | Critical - must fix |

---

## 6. Test Execution

### 6.1 Running Scheduler E2E Tests

```bash
# Run all scheduler E2E tests
python -m pytest tests/scheduler/test_e2e.py -v

# Run specific category
python -m pytest tests/scheduler/test_e2e.py::TestE2EJobGroup -v

# Run with coverage
python -m pytest tests/scheduler/test_e2e.py --cov=src/scheduler
```

### 6.2 Running Pipeline E2E Tests

```bash
# Prerequisites:
# - Set OPENAI_API_KEY or ANTHROPIC_API_KEY for external API tests
# - Start local Ollama for Ollama tests

# Run pipeline tests (when implemented)
python -m pytest tests/scheduler/test_pipeline_e2e.py -v --run-pipeline
```

---

## 7. Version Information

| Component | Version | Notes |
|-----------|---------|-------|
| Application | 1.5.0 | Managed by release-please |
| This Document | 1.0.0 | Independent versioning |
| Test Framework | pytest 9.0+ | With asyncio plugin |
| Python | 3.11+ | Required |

---

## Appendix A: Design Decision References

| Decision | Document | Impact on E2E |
|----------|----------|---------------|
| DEC-004 | DESIGN_GUARDS.md | Direct API reservation tests |
| DEC-007 | DESIGN_GUARDS.md | Retry flow tests |
| DEC-012 | DESIGN_GUARDS.md | JobGroup tests |
| INV-006 | DESIGN_GUARDS.md | Group completion atomicity |
