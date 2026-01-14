# Verification Notes - Phase 1 Critical Requirements

**Date:** 2026-01-08
**Purpose:** Explicit evidence that critical Phase 1 requirements are satisfied

---

## Critical Requirement 1: Graceful Shutdown

### Implementation Evidence

**File:** `main.py`

**Signal handler registration (lines 254-256):**
```python
# 신호 핸들러 등록
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

**Signal handler implementation (lines 26-35):**
```python
shutdown_requested = False

def signal_handler(signum, frame):
    """
    SIGINT / SIGTERM 핸들러 - 현재 생성 완료 후 종료
    """
    global shutdown_requested
    signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
    logger.info(f"\n{'=' * 80}")
    logger.info(f"{signal_name} 수신 - 현재 작업 완료 후 종료합니다")
    logger.info(f"{'=' * 80}")
    shutdown_requested = True
```

**Shutdown checks in main loop:**

1. **Before iteration starts (line 277-280):**
```python
# 종료 조건 체크
if shutdown_requested:
    logger.info("종료 신호 수신 - 루프 종료")
    break
```

2. **After iteration completes (line 324-327):**
```python
# 종료 조건 재확인 (현재 생성 완료 후)
if shutdown_requested:
    logger.info("종료 신호 수신 - 현재 생성 완료, 루프 종료")
    break
```

3. **During interval wait (line 334-340):**
```python
# 대기 중에도 종료 신호 확인 (1초 단위)
for _ in range(args.interval_seconds):
    if shutdown_requested:
        logger.info("대기 중 종료 신호 수신 - 루프 종료")
        break
    time.sleep(1)
if shutdown_requested:
    break
```

**Final statistics via finally block (line 347-365):**
```python
finally:
    # 최종 통계 출력
    end_time = time.time()
    total_duration = end_time - start_time

    logger.info("\n" + "=" * 80)
    logger.info("실행 완료 - 최종 통계")
    logger.info("=" * 80)
    logger.info(f"총 실행 시간: {total_duration:.1f}초 ...")
    logger.info(f"생성된 소설: {stories_generated}개")
    logger.info(f"총 토큰 사용량:")
    logger.info(f"  - Input tokens: {total_input_tokens:,}")
    logger.info(f"  - Output tokens: {total_output_tokens:,}")
    logger.info(f"  - Total tokens: {total_tokens:,}")
    ...
```

### Graceful Shutdown Flow

```
1. User presses Ctrl+C or system sends SIGTERM
   ↓
2. signal_handler() called
   ↓
3. shutdown_requested = True
   ↓
4. Current story generation continues (line 300: run_basic_generation())
   ↓
5. Story completes, result returned
   ↓
6. Statistics updated (lines 302-322)
   ↓
7. Shutdown check triggers (line 325)
   ↓
8. Loop breaks
   ↓
9. finally block executes (line 347)
   ↓
10. Final statistics logged (lines 352-365)
    ↓
11. Process exits cleanly (exit code 0)
```

### Verification Test

```bash
# Start operation
python main.py --max-stories 100 --interval-seconds 60 &
PID=$!

# Wait for first story to complete
sleep 120

# Send SIGINT
kill -SIGINT $PID

# Verify graceful exit
wait $PID
EXIT_CODE=$?

# Expected: EXIT_CODE = 0
echo "Exit code: $EXIT_CODE"

# Verify final stats logged
grep "실행 완료 - 최종 통계" logs/horror_story_*.log
```

**Expected log output:**
```
SIGINT 수신 - 현재 작업 완료 후 종료합니다
✓ 생성 완료 - 길이: ...
✓ 저장 위치: ...
종료 신호 수신 - 현재 생성 완료, 루프 종료

================================================================================
실행 완료 - 최종 통계
================================================================================
총 실행 시간: ...
생성된 소설: 1개
총 토큰 사용량:
  - Input tokens: ...
  - Output tokens: ...
```

### Critical Guarantees

✅ **Signal handled:** SIGINT and SIGTERM both registered
✅ **Non-interruptive:** Flag set only, no immediate exit
✅ **Completes current work:** Generation finishes before checking flag
✅ **Saves output:** `run_basic_generation()` completes → `save_story()` called
✅ **Logs usage:** Statistics updated before shutdown check
✅ **Always logs stats:** `finally` block ensures execution even on exception
✅ **Clean exit:** Natural loop break → process exits normally

---

## Critical Requirement 2: Usage Logging Reliability

### Implementation Evidence

**File:** `horror_story_generator.py`

**Defensive usage extraction (lines 407-422):**
```python
# Phase 1: Defensive usage extraction - handle missing usage gracefully
if hasattr(message, 'usage') and message.usage:
    try:
        usage = {
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
            "total_tokens": message.usage.input_tokens + message.usage.output_tokens
        }
        logger.info(f"소설 생성 완료 - 길이: {len(story_text)}자")
        logger.info(f"토큰 사용량 - Input: {usage['input_tokens']}, Output: {usage['output_tokens']}, Total: {usage['total_tokens']}")
    except (AttributeError, TypeError) as e:
        logger.warning(f"토큰 사용량 추출 실패 (usage 구조 이상): {e}")
        usage = None
else:
    logger.warning("토큰 사용량 정보 없음 (message.usage missing)")
    usage = None
```

**Usage propagation to metadata (horror_story_generator.py, line 709):**
```python
"metadata": {
    ...
    "usage": usage  # Can be None
}
```

**Safe statistics accumulation (main.py, lines 304-309):**
```python
if result and "metadata" in result:
    usage = result["metadata"].get("usage")
    if usage:
        total_input_tokens += usage.get("input_tokens", 0)
        total_output_tokens += usage.get("output_tokens", 0)
        total_tokens += usage.get("total_tokens", 0)
```

**Usage display with warning (main.py, lines 315-319):**
```python
if result["metadata"].get("usage"):
    usage = result["metadata"]["usage"]
    logger.info(f"✓ 토큰 사용: Input={usage['input_tokens']}, Output={usage['output_tokens']}, Total={usage['total_tokens']}")
else:
    logger.warning("⚠ 토큰 사용량 정보 없음")
```

### Usage Logging Flow - Success Case

```
1. API call succeeds: message = client.messages.create(...)
   ↓
2. Check: hasattr(message, 'usage') → True
   ↓
3. Check: message.usage → not None
   ↓
4. Extract: usage = { input_tokens: ..., output_tokens: ..., total_tokens: ... }
   ↓
5. Log: "토큰 사용량 - Input: X, Output: Y, Total: Z"
   ↓
6. Return: {"story_text": ..., "usage": {...}}
   ↓
7. Metadata: "usage": {...}
   ↓
8. Statistics: total_input_tokens += X, total_output_tokens += Y, total_tokens += Z
   ↓
9. Display: "✓ 토큰 사용: Input=X, Output=Y, Total=Z"
```

### Usage Logging Flow - Missing Usage Case

```
1. API call succeeds: message = client.messages.create(...)
   ↓
2. Check: hasattr(message, 'usage') → False (or message.usage → None)
   ↓
3. Warning: "토큰 사용량 정보 없음 (message.usage missing)"
   ↓
4. Fallback: usage = None
   ↓
5. Return: {"story_text": ..., "usage": None}
   ↓
6. Metadata: "usage": null
   ↓
7. Statistics: usage is None → skip accumulation (if usage: ... not executed)
   ↓
8. Display: "⚠ 토큰 사용량 정보 없음"
   ↓
9. Process continues (NO CRASH)
```

### Usage Logging Flow - Extraction Error Case

```
1. API call succeeds: message = client.messages.create(...)
   ↓
2. Check: hasattr(message, 'usage') and message.usage → True
   ↓
3. Extract: usage["input_tokens"] = message.usage.input_tokens → AttributeError raised
   ↓
4. Exception caught: except (AttributeError, TypeError) as e
   ↓
5. Warning: "토큰 사용량 추출 실패 (usage 구조 이상): {e}"
   ↓
6. Fallback: usage = None
   ↓
7-9. Same as missing usage case above
```

### Verification Test

**Test 1: Normal operation (usage present)**
```bash
python main.py --max-stories 1

# Expected log:
# "토큰 사용량 - Input: 1234, Output: 5678, Total: 6912"
# "✓ 토큰 사용: Input=1234, Output=5678, Total=6912"
# "총 토큰 사용량:"
# "  - Input tokens: 1,234"
# "  - Output tokens: 5,678"
# "  - Total tokens: 6,912"
```

**Test 2: Missing usage (simulated via API mock)**
```python
# In test environment, if API returns message with usage=None:

# Expected log:
# "토큰 사용량 정보 없음 (message.usage missing)"
# "⚠ 토큰 사용량 정보 없음"
# "총 토큰 사용량:"
# "  - Input tokens: 0"
# "  - Output tokens: 0"
# "  - Total tokens: 0"

# Expected metadata:
# { ..., "usage": null }

# Expected: NO CRASH, process continues
```

**Test 3: Extraction error (simulated via monkey patch)**
```python
# If message.usage.input_tokens raises AttributeError:

# Expected log:
# "토큰 사용량 추출 실패 (usage 구조 이상): 'Usage' object has no attribute 'input_tokens'"
# "⚠ 토큰 사용량 정보 없음"

# Expected: NO CRASH, process continues
```

### Verification Commands

```bash
# Check for successful usage logging
grep "토큰 사용량 - Input:" logs/horror_story_*.log

# Check for warnings (should be empty in normal operation)
grep "토큰 사용량.*없음" logs/horror_story_*.log
grep "토큰 사용량 추출 실패" logs/horror_story_*.log

# Check for crashes (should be empty)
grep "Traceback" logs/horror_story_*.log
grep "AttributeError" logs/horror_story_*.log | grep -v "토큰 사용량 추출 실패"

# Verify final statistics always present
grep "총 토큰 사용량" logs/horror_story_*.log
```

### Critical Guarantees

✅ **Null check:** `hasattr(message, 'usage') and message.usage` prevents AttributeError
✅ **Exception handling:** `try/except` catches extraction errors
✅ **Warning logged:** Both missing and error cases log warning (not error)
✅ **Fallback value:** `usage = None` when unavailable
✅ **No crash:** Process continues after setting usage=None
✅ **Safe propagation:** `usage.get("input_tokens", 0)` with default prevents KeyError
✅ **Metadata preserved:** usage=null stored in metadata JSON
✅ **Statistics skip:** `if usage:` prevents accumulation of None
✅ **Display warning:** User informed via "⚠ 토큰 사용량 정보 없음"

---

## Coverage Matrix

| Phase 1 Requirement | Implementation | Evidence |
|---------------------|---------------|----------|
| **1. Background execution** | Loop with CLI args | Lines 240-365 in main.py |
| **2. Real-time observability** | Existing logging verified | Audit finding 4 (lines 22-73 in horror_story_generator.py) |
| **3. Output continuity** | Existing save logic verified | Audit finding 2 (generate_horror_story() unchanged) |
| **4. Graceful shutdown** | Signal handlers + checks | Lines 23-35, 254-256, 277-340 in main.py |
| **5. Usage logging reliability** | Defensive extraction | Lines 407-422 in horror_story_generator.py |

---

## Test Execution Order

For complete verification, execute in this order:

1. **Single generation test** (baseline)
   ```bash
   python main.py
   ```

2. **Multiple generation test** (loop verification)
   ```bash
   python main.py --max-stories 3 --interval-seconds 60
   ```

3. **Graceful shutdown test** (SIGINT handling)
   ```bash
   python main.py --max-stories 100 --interval-seconds 60 &
   sleep 120
   kill -SIGINT $!
   ```

4. **24-hour test** (full operational verification)
   ```bash
   nohup python main.py --duration-seconds 86400 --interval-seconds 1800 > output_24h.log 2>&1 &
   ```

---

## Sign-off Criteria

Phase 1 passes if ALL of the following are verified:

- [ ] Graceful shutdown: SIGINT/SIGTERM handled, current work completes, stats logged, clean exit
- [ ] Usage logging: Normal case logs tokens; missing case logs warning (not crash)
- [ ] Background execution: Process runs for specified duration/count
- [ ] Observability: Logs written to stdout and file
- [ ] Output continuity: All stories complete, metadata present, no partial outputs

---

**Verification Status:** ✅ IMPLEMENTATION COMPLETE - READY FOR TESTING
**Critical Requirements:** ✅ BOTH ADDRESSED WITH EVIDENCE
**Test Runbook:** See `docs/runbook_24h_test.md`
