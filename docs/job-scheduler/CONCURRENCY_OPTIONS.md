# OQ-001: Concurrency Limit Strategy — Decision Pack

> **Status:** DECISION PENDING
> **Phase:** 3-B
> **Last Updated:** 2026-01-18

---

## Problem Statement

**Why This Matters Now**:
- CON-002 (Ollama Resource Exclusivity) requires single-job execution for local LLM
- Future use cases may need parallel execution for remote APIs
- Dispatcher implementation is blocked until concurrency model is chosen
- Test strategy (TEST_STRATEGY.md) needs to know which tests to add

**Current Constraint**: Single-worker assumed. Decision affects how we scale beyond this.

---

## Options

### Option A: Global Single Concurrency (Baseline)

**Description**: Maximum 1 job running at any time, regardless of type or resource.

| Aspect | Assessment |
|--------|------------|
| **Pros** | Simplest implementation; No resource conflicts; Matches current constraint |
| **Cons** | Cannot parallelize even independent tasks; Underutilizes remote API capacity |
| **Operational Risk** | Low — predictable, no race conditions |
| **Components Affected** | Dispatcher (trivial check) |
| **Persistence Impact** | None — no new fields needed |
| **Test Impact** | All existing INV-003-* tests remain valid; No new tests needed |

---

### Option B: Per-Type Concurrency

**Description**: Separate concurrency limits per job_type (e.g., max 1 story, max 2 research).

| Aspect | Assessment |
|--------|------------|
| **Pros** | Allows parallel research while story uses Ollama; Simple mental model |
| **Cons** | Doesn't distinguish within type (all research treated same); Config per type |
| **Operational Risk** | Medium — must configure limits correctly |
| **Components Affected** | Dispatcher (count by type), Config |
| **Persistence Impact** | Add `concurrency_limits` config table or static config |
| **Test Impact** | Add INV-003-C/D for multi-type scenarios; Existing single-worker tests remain valid |

**Example Config**:
```
story: 1        # Uses Ollama, exclusive
research: 2     # Can use remote API, parallelizable
```

---

### Option C: Resource-Based Concurrency

**Description**: Tag jobs with resource requirements; limit by resource pool.

| Aspect | Assessment |
|--------|------------|
| **Pros** | Most flexible; Handles mixed models (ollama vs claude vs cpu-bound) |
| **Cons** | Complex tagging; More config; Harder to reason about |
| **Operational Risk** | High — misconfigured tags cause resource conflicts |
| **Components Affected** | Dispatcher, JobTemplate, Job entity, Config |
| **Persistence Impact** | Add `resource_tags` to Job/JobTemplate; Add `resource_pools` config |
| **Test Impact** | Significant new test surface; Must test tag inheritance and pool limits |

**Example Config**:
```
resources:
  ollama: 1       # Local LLM
  claude-api: 3   # Remote, can parallelize
  cpu-bound: 2    # CPU-intensive tasks
```

---

## Comparison Matrix

| Criteria | Option A | Option B | Option C |
|----------|----------|----------|----------|
| Implementation Effort | Trivial | Low | Medium-High |
| Flexibility | None | Moderate | High |
| Operational Complexity | None | Low | Medium |
| Risk of Misconfiguration | None | Low | Medium |
| Future-Proof | Limited | Good | Excellent |
| Matches Current Constraint | Perfect | Good | Good |

---

## Recommendation

**Default for Phase 4: Option A (Global Single Concurrency)**

**Rationale**:
1. **Matches CON-002**: Ollama exclusivity requires single execution anyway
2. **Zero implementation overhead**: Dispatcher already assumes single worker
3. **No configuration risk**: Nothing to misconfigure
4. **Fastest path to working scheduler**: Unblocks Phase 4 immediately

**Migration Path to Option B/C**:
```
Phase 4: Ship with Option A (global=1)
Phase 5+: When remote API parallelization needed:
  1. Add job_type or resource_tags field (already placeholder in schema)
  2. Update Dispatcher to count by type/resource
  3. Add configuration
  4. Existing tests remain valid (single-worker is subset)
```

**No locked decisions affected**: DEC-004~DEC-010 remain unchanged.

---

## Decision Checklist

- [ ] Confirm Option A as Phase 4 default
- [ ] Defer Option B/C to future phase
- [ ] Update DESIGN_GUARDS.md to promote OQ-001 → DEC-011
- [ ] No persistence schema changes needed for Phase 4

