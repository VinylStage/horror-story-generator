# OQ-002: JobGroup Sequential Failure Behavior — Decision Pack

> **Status:** RESOLVED → DEC-012
> **Document Version:** 1.0.0
> **Application Version:** 1.5.0 (managed by release-please)
> **Last Updated:** 2026-01-18
>
> **Decision**: Option A selected — Stop-on-failure.
> See DESIGN_GUARDS.md DEC-012 for the canonical decision.

---

## Problem Statement

**Why This Matters Now**:
- JobGroup entity exists in DOMAIN_MODEL.md with `mode: sequential | parallel`
- Sequential mode needs defined behavior when a member job fails
- INV-006 (JobGroup Completion Atomicity) is testable but failure behavior is not
- Batch API (`/jobs/batch/trigger`) maps to JobGroup; users expect predictable behavior

**Question**: When Job2 in a sequential group [Job1, Job2, Job3] fails, what happens to Job3?

---

## Options

### Option A: Stop-on-Failure (Fail-Fast)

**Description**: If any job fails, cancel remaining jobs in the sequence.

| Aspect | Assessment |
|--------|------------|
| **Pros** | Predictable; Prevents wasted work; Clear error semantics |
| **Cons** | No partial results; All-or-nothing |
| **Operational Implication** | Logs show: "Job3 CANCELLED due to Job2 failure" |
| **API Fields** | None required — this is default behavior |
| **Persistence Impact** | None — existing status fields sufficient |
| **Test Impact** | INV-006-C covers this; Add test for CANCELLED propagation |

**Behavior**:
```
Job1: COMPLETED
Job2: FAILED
Job3: CANCELLED (never started)
Group: PARTIAL
```

---

### Option B: Continue-on-Failure (Best-Effort)

**Description**: Execute all jobs regardless of failures; collect results at end.

| Aspect | Assessment |
|--------|------------|
| **Pros** | Maximum work attempted; Good for independent tasks |
| **Cons** | May waste resources on doomed work; Unclear if results are usable |
| **Operational Implication** | Logs show: "Job3 executed despite Job2 failure" |
| **API Fields** | None required — behavior change only |
| **Persistence Impact** | None |
| **Test Impact** | Add test for continued execution after failure |

**Behavior**:
```
Job1: COMPLETED
Job2: FAILED
Job3: COMPLETED (executed anyway)
Group: PARTIAL
```

---

### Option C: Configurable Policy

**Description**: Allow per-group configuration via `on_failure` field.

| Aspect | Assessment |
|--------|------------|
| **Pros** | Maximum flexibility; Users choose per use case |
| **Cons** | More complexity; Must validate configuration |
| **Operational Implication** | Logs show policy used: "Policy: stop" or "Policy: continue" |
| **API Fields** | Add `on_failure: stop | continue | skip` to JobGroup/Batch API |
| **Persistence Impact** | Add `on_failure` column to job_groups table |
| **Test Impact** | 3 test paths instead of 1; Configuration validation tests |

**API Example**:
```json
POST /api/jobs/batch
{
  "jobs": [...],
  "mode": "sequential",
  "on_failure": "stop"
}
```

**Policy Values**:
| Policy | Behavior |
|--------|----------|
| `stop` | Cancel remaining (Option A) |
| `continue` | Execute all (Option B) |
| `skip` | Skip remaining without CANCELLED status |

---

## Comparison Matrix

| Criteria | Option A | Option B | Option C |
|----------|----------|----------|----------|
| Implementation Effort | Trivial | Trivial | Low |
| User Flexibility | None | None | High |
| API Surface Change | None | None | +1 field |
| Predictability | High | Medium | High (explicit) |
| Default Behavior Clarity | Clear | Clear | Must document default |

---

## Recommendation

**Default for Phase 4: Option A (Stop-on-Failure)**

**Rationale**:
1. **Safest default**: Prevents cascading failures and wasted resources
2. **Predictable semantics**: Users expect sequential to mean "dependent"
3. **No API changes**: Matches current batch API
4. **Existing tests valid**: INV-006-C already tests this scenario

**Upgrade Path to Option C**:
```
Phase 4: Ship with Option A as default
Phase 5+: When user requests flexibility:
  1. Add on_failure field to JobGroup/Batch API
  2. Default value: "stop" (backward compatible)
  3. Implement continue/skip handlers
  4. Existing tests remain valid (stop is default)
```

**No locked decisions affected**: DEC-004~DEC-010 remain unchanged.

---

## Interaction with Retry (DEC-007)

**Question**: Does a failed job get retried before group decides to stop?

**Answer**: Yes.
```
Job2 fails → RetryController creates Job2-retry (if eligible)
           → Group waits for retry chain to exhaust
           → If all retries fail → then stop remaining jobs
           → Job3 cancelled only after Job2 permanently fails
```

This ensures retry semantics are respected before group-level decisions.

---

## Decision Checklist

- [ ] Confirm Option A as Phase 4 default
- [ ] Document retry-before-stop interaction
- [ ] Defer Option C to future phase
- [ ] Update DESIGN_GUARDS.md to promote OQ-002 → DEC-012
- [ ] No persistence schema changes needed for Phase 4

