# 24-Hour Continuous Operation Test - Runbook

**Version:** 1.0
**Date:** 2026-01-08
**Phase:** Phase 1 Operational Verification

---

## Purpose

This runbook provides procedures to verify that the horror story generator can run continuously for 24 hours without:
- Data loss
- Silent failures
- Unreliable logging
- Inability to shutdown gracefully

---

## Prerequisites

### Environment Setup

1. **API Key:**
   ```bash
   # Ensure .env file exists with valid API key
   cat .env | grep ANTHROPIC_API_KEY
   ```

2. **Dependencies:**
   ```bash
   # Python 3.8+ required
   python --version

   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Disk Space:**
   ```bash
   # Ensure sufficient space for logs and stories
   # Estimate: ~50KB per story, ~10KB per log entry
   # For 24h at 30min intervals: ~48 stories = ~3MB
   df -h .
   ```

---

## Test Scenarios

### Scenario 1: Short Verification Test (15 minutes)

**Purpose:** Verify all mechanisms work before long-running test

```bash
# Generate 3 stories at 5-minute intervals
python main.py --max-stories 3 --interval-seconds 300
```

**Expected outcome:**
- 3 stories generated
- Files saved in `generated_stories/`
- Logs written to `logs/horror_story_YYYYMMDD_HHMMSS.log`
- Final statistics printed

**Verification:**
```bash
# Check story files
ls -lh generated_stories/horror_story_*.md | tail -3

# Check log file
tail -50 logs/horror_story_*.log

# Verify token usage logged
grep "토큰 사용량" logs/horror_story_*.log
```

---

### Scenario 2: 24-Hour Continuous Operation

**Purpose:** Full Phase 1 operational verification

```bash
# Run for 24 hours with 30-minute intervals
# Expected: ~48 stories generated
nohup python main.py \
  --duration-seconds 86400 \
  --interval-seconds 1800 \
  > output_24h.log 2>&1 &

# Save process ID
echo $! > generator.pid
```

**Monitor during operation:**

```bash
# Check process is running
ps -p $(cat generator.pid)

# Monitor real-time logs (stdout + stderr)
tail -f output_24h.log

# Monitor file logs
tail -f logs/horror_story_*.log

# Check stories generated so far
ls generated_stories/ | wc -l

# Check disk usage
du -sh generated_stories/ logs/
```

**After 24 hours:**

```bash
# Verify process completed
ps -p $(cat generator.pid) || echo "Process completed"

# Check final statistics
tail -20 output_24h.log

# Count generated stories
ls generated_stories/horror_story_*.md | wc -l

# Verify all have metadata
ls generated_stories/horror_story_*_metadata.json | wc -l
```

---

### Scenario 3: Graceful Shutdown Test

**Purpose:** Verify SIGINT/SIGTERM handling

```bash
# Start long-running operation
python main.py --max-stories 100 --interval-seconds 60 &
PID=$!

# Wait for first story to complete
sleep 120

# Send SIGINT (Ctrl+C equivalent)
kill -SIGINT $PID

# Verify graceful shutdown
wait $PID
echo "Exit code: $?"
```

**Expected behavior:**
1. Current story generation completes
2. Results saved
3. Final statistics logged
4. Process exits with code 0

**Verification:**
```bash
# Check last log entries
tail -30 logs/horror_story_*.log

# Verify final story is complete (not truncated)
tail -20 generated_stories/horror_story_*.md | head -10

# Verify metadata saved
cat generated_stories/horror_story_*_metadata.json | jq .
```

---

### Scenario 4: Usage Logging Resilience Test

**Purpose:** Verify system handles missing token usage gracefully

**Note:** This test cannot be directly triggered without API mocking. During normal operation, if API returns no usage data, verify:

```bash
# Search for warning messages
grep "토큰 사용량 정보 없음" logs/horror_story_*.log
grep "토큰 사용량 추출 실패" logs/horror_story_*.log

# Verify process did NOT crash
# Check for complete execution logs
grep "실행 완료 - 최종 통계" logs/horror_story_*.log
```

---

## Stop Conditions

The generator stops when ANY of the following occurs:

1. **Duration limit reached** (`--duration-seconds`)
   ```
   실행 시간 제한 도달 (86400.0초) - 루프 종료
   ```

2. **Story count limit reached** (`--max-stories`)
   ```
   생성 개수 제한 도달 (10개) - 루프 종료
   ```

3. **SIGINT received** (Ctrl+C)
   ```
   SIGINT 수신 - 현재 작업 완료 후 종료합니다
   ```

4. **SIGTERM received** (system shutdown)
   ```
   SIGTERM 수신 - 현재 작업 완료 후 종료합니다
   ```

---

## Success Criteria

Phase 1 passes if ALL of the following are verified:

### 1. Background Execution ✓
- [ ] Process runs unattended for full duration
- [ ] No interactive prompts or hangs
- [ ] Process continues after terminal disconnect (nohup)

### 2. Real-time Observability ✓
- [ ] Logs visible in stdout
- [ ] Logs persisted to `logs/horror_story_YYYYMMDD_HHMMSS.log`
- [ ] Log entries timestamped
- [ ] Log file readable during execution

### 3. Output Continuity ✓
- [ ] All stories successfully generated
- [ ] Each story has corresponding `.md` file
- [ ] Each story has corresponding `_metadata.json` file
- [ ] No partial or truncated outputs
- [ ] Markdown files have valid YAML frontmatter

### 4. Graceful Shutdown ✓
- [ ] SIGINT handled correctly
- [ ] SIGTERM handled correctly
- [ ] Current generation completes before exit
- [ ] Output saved
- [ ] Final statistics logged
- [ ] Process exits cleanly (exit code 0)
- [ ] No interrupted iterations (check last story is complete)

### 5. Usage Logging Reliability ✓
- [ ] Token usage logged for each generation
- [ ] Input/output/total tokens all present
- [ ] Final statistics show cumulative token usage
- [ ] If usage missing: warning logged (NOT crash)
- [ ] If usage missing: `usage: null` in metadata
- [ ] Average tokens/story calculated correctly

---

## Troubleshooting

### Problem: Process exits immediately

```bash
# Check for errors
tail -50 logs/horror_story_*.log

# Common causes:
# - Missing ANTHROPIC_API_KEY
# - Invalid API key
# - Missing dependencies
```

**Solution:**
```bash
# Verify API key
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('ANTHROPIC_API_KEY'))"

# Test single generation first
python main.py --max-stories 1
```

---

### Problem: Logs not updating

```bash
# Check if process is running
ps aux | grep "python main.py"

# Check if log file is being written
ls -lh logs/

# Check stdout/stderr
tail -f output_24h.log
```

**Solution:**
- Verify process PID matches
- Check disk space (`df -h`)
- Check file permissions (`ls -la logs/`)

---

### Problem: Shutdown takes too long

**Expected behavior:**
- Shutdown initiated immediately
- Current generation completes (may take 30-120 seconds)
- Final statistics logged
- Exit

**If hanging:**
```bash
# Send SIGTERM after SIGINT
kill -SIGTERM $(cat generator.pid)

# Force kill only as last resort (loses current generation)
kill -9 $(cat generator.pid)
```

---

### Problem: Token usage shows 0 or null

**Check logs:**
```bash
grep -A5 "토큰 사용량" logs/horror_story_*.log
```

**If warning present:**
```
⚠ 토큰 사용량 정보 없음
```

**This is expected behavior** if API doesn't return usage. Verify:
- [ ] Warning logged (not error)
- [ ] Process continues
- [ ] Story still saved
- [ ] Metadata has `"usage": null`

---

## Verification Checklist

After completing 24h test, verify all criteria:

```bash
# 1. Background execution
ps -p $(cat generator.pid) && echo "FAIL: Still running" || echo "PASS: Completed"

# 2. Observability
ls logs/horror_story_*.log && echo "PASS: Log file exists"
wc -l logs/horror_story_*.log  # Should have many lines

# 3. Output continuity
STORY_COUNT=$(ls generated_stories/horror_story_*.md 2>/dev/null | wc -l)
METADATA_COUNT=$(ls generated_stories/horror_story_*_metadata.json 2>/dev/null | wc -l)
echo "Stories: $STORY_COUNT, Metadata: $METADATA_COUNT"
[ "$STORY_COUNT" -eq "$METADATA_COUNT" ] && echo "PASS: Output complete"

# 4. Graceful shutdown
grep "실행 완료 - 최종 통계" logs/horror_story_*.log && echo "PASS: Graceful exit"

# 5. Usage logging
grep "총 토큰 사용량" logs/horror_story_*.log && echo "PASS: Usage logged"
```

---

## CLI Reference

```
usage: main.py [-h] [--duration-seconds DURATION_SECONDS]
               [--max-stories MAX_STORIES]
               [--interval-seconds INTERVAL_SECONDS]

optional arguments:
  -h, --help            show this help message and exit
  --duration-seconds DURATION_SECONDS
                        실행 지속 시간(초). 지정하지 않으면 --max-stories 또는
                        수동 종료까지 실행
  --max-stories MAX_STORIES
                        생성할 최대 소설 개수. 기본값=1 (단일 실행)
  --interval-seconds INTERVAL_SECONDS
                        소설 생성 간 대기 시간(초). 기본값=0 (대기 없음)
```

**Examples:**

```bash
# Single generation (default, backward compatible)
python main.py

# Generate 5 stories immediately
python main.py --max-stories 5

# Run for 1 hour, 15min intervals
python main.py --duration-seconds 3600 --interval-seconds 900

# Run for 24 hours, 30min intervals
python main.py --duration-seconds 86400 --interval-seconds 1800

# Infinite mode (stop with Ctrl+C)
python main.py --max-stories 999999 --interval-seconds 600
```

---

## Post-Test Analysis

After successful 24h run:

```bash
# Generate summary report
echo "=== 24H TEST SUMMARY ===" > test_summary.txt
echo "Test completed: $(date)" >> test_summary.txt
echo "" >> test_summary.txt

# Story count
echo "Stories generated: $(ls generated_stories/horror_story_*.md | wc -l)" >> test_summary.txt

# Total size
echo "Total story size: $(du -sh generated_stories/ | cut -f1)" >> test_summary.txt
echo "Total log size: $(du -sh logs/ | cut -f1)" >> test_summary.txt

# Extract final stats from log
echo "" >> test_summary.txt
echo "=== FINAL STATISTICS ===" >> test_summary.txt
tail -20 logs/horror_story_*.log >> test_summary.txt

cat test_summary.txt
```

---

## Notes

- **Backward compatibility:** Running `python main.py` with no arguments still generates a single story (default: `--max-stories 1`)
- **Graceful degradation:** If token usage is unavailable, process continues with warning
- **Log file persistence:** One log file per process execution (filename includes start timestamp)
- **No interruption during generation:** SIGINT/SIGTERM only stop after current story completes

---

## Next Steps (Out of Scope for Phase 1)

Phase 1 verification ends here. The following are explicitly NOT implemented:

- ❌ KU / Canonical integration
- ❌ Story validation
- ❌ Platform upload
- ❌ Distributed execution
- ❌ Database persistence

Phase 2 will address these if requirements specify them.
