# TASK 6: Human-Executable 정리 계획

**작성일:** 2026-01-12
**상태:** 계획 (실행 전 확인 필요)
**주의:** 이 문서는 실행 계획만 포함. 실제 실행은 Human이 직접 수행.

---

## 실행 전 체크리스트

- [ ] Git 상태 확인 (`git status` - 커밋되지 않은 변경 없음)
- [ ] 백업 생성 (선택사항)
- [ ] 각 단계 실행 전 검토 완료

---

## Phase 1: 디렉토리 준비 (Step 1-3)

### Step 1: archive 디렉토리 생성

```bash
mkdir -p archive/legacy_docs
mkdir -p archive/raw_research
mkdir -p archive/canonical_abstraction
```

**확인 사항:** 디렉토리가 생성되었는지 `ls -la archive/` 로 확인

---

### Step 2: assets 디렉토리 생성

```bash
mkdir -p assets/knowledge_units
mkdir -p assets/templates
```

**확인 사항:** 디렉토리가 생성되었는지 확인

---

### Step 3: data 디렉토리 정리 준비

```bash
mkdir -p data/db
mkdir -p data/output/stories
mkdir -p data/output/research
```

**확인 사항:** 기존 data/ 내용과 충돌 없는지 확인

---

## Phase 2: Phase 문서 아카이브 (Step 4-7)

### Step 4: 루트 Phase 문서 이동

```bash
# [Human confirmation required] 이동 전 파일 내용 확인
mv PHASE1_IMPLEMENTATION_SUMMARY.md archive/legacy_docs/
```

---

### Step 5: docs/ Phase 문서 아카이브

```bash
# 아카이브 대상
mv docs/PHASE2_PREPARATION_ANALYSIS.md archive/legacy_docs/
mv docs/PHASE2A_TEMPLATE_ACTIVATION.md archive/legacy_docs/
mv docs/PHASE2B_GENERATION_MEMORY.md archive/legacy_docs/

# [Human confirmation required] 통합 후 삭제할 문서 (일단 아카이브)
mv docs/PHASE2C_DEDUP_CONTROL.md archive/legacy_docs/
mv docs/PHASE_B_PLUS.md archive/legacy_docs/
```

---

### Step 6: docs/phase_b/ 디렉토리 처리

```bash
# 전체 phase_b 디렉토리 아카이브
mv docs/phase_b archive/legacy_docs/

# 또는 개별 파일 처리:
# mv docs/phase_b/overview.md archive/legacy_docs/
# mv docs/phase_b/dedup_signal_policy.md archive/legacy_docs/
# mv docs/phase_b/research_quality_schema.md archive/legacy_docs/
# mv docs/phase_b/cultural_scope_strategy.md archive/legacy_docs/
# mv docs/phase_b/future_vector_backend.md archive/legacy_docs/
# rmdir docs/phase_b
```

---

### Step 7: 삭제 대상 Phase 문서 처리

```bash
# [Human confirmation required] 삭제 전 최종 확인
# 옵션 A: 직접 삭제
# rm docs/PHASE2C_RESEARCH_JOB.md

# 옵션 B: 아카이브로 이동 (권장)
mv docs/PHASE2C_RESEARCH_JOB.md archive/legacy_docs/
```

---

## Phase 3: 데이터 자산 이동 (Step 8-11)

### Step 8: Knowledge Units 이동

```bash
# [Human confirmation required] 코드 경로 수정 전 이동하면 오류 발생
# 코드 수정 완료 후 실행할 것

# 복사 후 원본 유지 (안전)
cp -r phase1_foundation/01_knowledge_units/* assets/knowledge_units/

# 원본 이동 (코드 수정 후)
# mv phase1_foundation/01_knowledge_units/* assets/knowledge_units/
```

**코드 수정 필요:**
- `ku_selector.py` 내 `KU_DIR` 경로 변경

---

### Step 9: Templates 이동

```bash
# 복사 후 원본 유지 (안전)
cp -r phase1_foundation/03_templates/* assets/templates/

# 원본 이동 (코드 수정 후)
# mv phase1_foundation/03_templates/* assets/templates/
```

**코드 수정 필요:**
- `template_manager.py` 내 `TEMPLATE_DIR` 경로 변경

---

### Step 10: Raw Research 아카이브

```bash
mv phase1_foundation/00_raw_research/* archive/raw_research/
```

---

### Step 11: Canonical Abstraction 아카이브

```bash
mv phase1_foundation/02_canonical_abstraction/* archive/canonical_abstraction/
```

---

## Phase 4: 레거시 정리 (Step 12-14)

### Step 12: phase1_foundation 디렉토리 제거

```bash
# [Human confirmation required] 모든 파일 이동 완료 확인 후 실행
# 빈 디렉토리 확인
ls -la phase1_foundation/

# 빈 디렉토리 제거
rmdir phase1_foundation/00_raw_research
rmdir phase1_foundation/01_knowledge_units
rmdir phase1_foundation/02_canonical_abstraction
rmdir phase1_foundation/03_templates
rmdir phase1_foundation
```

---

### Step 13: phase2_execution 디렉토리 확인 및 처리

```bash
# [Human confirmation required] 내용 확인
ls -la phase2_execution/

# 필요한 파일은 아카이브
# mv phase2_execution/* archive/legacy_docs/

# 빈 디렉토리 제거
# rmdir phase2_execution
```

---

### Step 14: generated_stories 레거시 처리

```bash
# [Human confirmation required] 기존 스토리 보존 필요 여부 확인

# 옵션 A: data/output/stories로 통합
mv generated_stories/* data/output/stories/
rmdir generated_stories

# 옵션 B: 아카이브
mv generated_stories archive/

# 옵션 C: 유지 (현재 동작 유지)
```

---

## Phase 5: 데이터베이스 정리 (Step 15-16)

### Step 15: DB 파일 이동

```bash
# [Human confirmation required] 코드 경로 수정 전 이동하면 오류 발생

# 복사 후 원본 유지 (안전)
cp data/stories.db data/db/stories.db
cp data/research_registry.db data/db/research_registry.db

# 코드 수정 후 원본 삭제
# rm data/stories.db
# rm data/research_registry.db
```

**코드 수정 필요:**
- `story_registry.py` 내 `DB_PATH` 경로 변경
- `research_dedup_manager.py` 내 DB 경로 변경

---

### Step 16: Output 디렉토리 이동

```bash
# [Human confirmation required] 경로 수정 필요

# 복사 후 원본 유지
cp -r data/stories/* data/output/stories/
cp -r data/research/* data/output/research/

# 코드 수정 후 원본 삭제
# rm -r data/stories
# rm -r data/research
```

---

## Phase 6: 문서 통합 (Step 17-20)

### Step 17: docs/analysis 생성 확인

```bash
# 이미 생성됨 (본 분석 문서 위치)
ls -la docs/analysis/
```

---

### Step 18: 새 문서 디렉토리 생성

```bash
mkdir -p docs/schemas
mkdir -p docs/guides
mkdir -p docs/decisions
mkdir -p docs/changelog/releases
```

---

### Step 19: 통합 문서 작성 (별도 작업)

다음 문서를 새로 작성해야 함:
- [ ] `docs/architecture.md` (PHASE_B_PLUS 기반)
- [ ] `docs/api-reference.md` (TRIGGER_API 확장)
- [ ] `docs/cli-reference.md` (신규)
- [ ] `docs/schemas/story.md`
- [ ] `docs/schemas/research-card.md`
- [ ] `docs/schemas/job.md`
- [ ] `docs/guides/getting-started.md`
- [ ] `docs/changelog/CHANGELOG.md`

---

### Step 20: README.md 업데이트 (별도 작업)

- [ ] Phase 기반 설명 제거
- [ ] 버전 기반 설명 추가
- [ ] Getting Started 링크 추가
- [ ] 문서 인덱스 추가

---

## Phase 7: 코드 수정 (Step 21-24)

### Step 21: 경로 상수 수정

**수정 필요 파일 목록:**

| 파일 | 수정 대상 | 변경 내용 |
|------|----------|----------|
| `ku_selector.py` | `KU_DIR` | `phase1_foundation/01_knowledge_units` → `assets/knowledge_units` |
| `template_manager.py` | `TEMPLATE_DIR` | `phase1_foundation/03_templates` → `assets/templates` |
| `story_saver.py` | `OUTPUT_DIR` | 필요시 경로 수정 |
| `story_registry.py` | `DB_PATH` | `data/stories.db` → `data/db/stories.db` |
| `job_manager.py` | `JOBS_DIR` | 필요시 경로 수정 |
| `job_monitor.py` | 경로 상수 | 필요시 경로 수정 |

---

### Step 22: 테스트 실행

```bash
# 모든 테스트 실행
pytest tests/ -v

# 특정 테스트 실행
pytest tests/test_ku_selector.py -v
pytest tests/test_template_manager.py -v
```

---

### Step 23: 수동 동작 테스트

```bash
# 스토리 생성 테스트
python main.py --max-stories 1

# 리서치 생성 테스트
python -m research_executor run "테스트 토픽" --tags test

# API 서버 테스트
uvicorn research_api.main:app --port 8000 &
curl http://localhost:8000/jobs
```

---

### Step 24: Git 커밋

```bash
# 변경 확인
git status
git diff

# 커밋
git add .
git commit -m "refactor: remove phase-based naming, reorganize directory structure

- Move phase1_foundation assets to assets/ directory
- Archive legacy Phase documents to archive/
- Update path constants in code
- Reorganize data directory structure

BREAKING CHANGE: Directory paths have changed. Update any external references.
"
```

---

## 실행 순서 요약

| 순서 | Step | 설명 | 코드 수정 필요 |
|------|------|------|---------------|
| 1 | Step 1-3 | 디렉토리 준비 | 아니오 |
| 2 | Step 4-7 | Phase 문서 아카이브 | 아니오 |
| 3 | Step 21 | **코드 경로 수정** | **예** |
| 4 | Step 8-11 | 데이터 자산 이동 | 아니오 |
| 5 | Step 12-14 | 레거시 정리 | 아니오 |
| 6 | Step 15-16 | DB 정리 | 아니오 (이미 수정됨) |
| 7 | Step 22-23 | 테스트 | 아니오 |
| 8 | Step 17-20 | 문서 통합 | 아니오 |
| 9 | Step 24 | Git 커밋 | 아니오 |

---

## Human Confirmation Required 체크리스트

- [ ] phase2_execution 디렉토리 내용 확인
- [ ] generated_stories 처리 방향 결정
- [ ] 삭제 대상 문서 최종 확인
- [ ] 코드 경로 수정 범위 확인
- [ ] 테스트 통과 확인

---

## 롤백 계획

문제 발생 시:

```bash
# Git으로 롤백
git checkout -- .

# 또는 특정 파일만 롤백
git checkout -- path/to/file

# 커밋 후 롤백 필요시
git revert HEAD
```

---

**문서 끝**
